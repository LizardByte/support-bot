# standard imports
from datetime import datetime
import os
import shelve
import sys
import threading
import time

# lib imports
import discord
import praw
from praw import models

# local imports
from src.common import common
from src.common import globals


class Bot:
    def __init__(self, **kwargs):
        self.STOP_SIGNAL = False

        # threads
        self.bot_thread = threading.Thread(target=lambda: None)
        self.comment_thread = threading.Thread(target=lambda: None)
        self.submission_thread = threading.Thread(target=lambda: None)

        # ensure we have all required environment variables
        self.env_valid = self.validate_env()

        self.version = kwargs.get('version', 'v1')
        self.user_agent = kwargs.get('user_agent', f'{common.bot_name} {self.version}')
        self.avatar = kwargs.get('avatar', common.get_bot_avatar(gravatar=os.environ['GRAVATAR_EMAIL']))
        self.subreddit_name = kwargs.get('subreddit', os.getenv('PRAW_SUBREDDIT', 'LizardByte'))
        self.redirect_uri = kwargs.get('redirect_uri', os.getenv('REDIRECT_URI', 'http://localhost:8080'))

        # directories
        self.data_dir = common.data_dir
        self.commands_dir = os.path.join(self.data_dir, "support-bot-commands", "docs")

        # files
        self.db = os.path.join(self.data_dir, 'reddit_bot_database')

        # locks
        self.lock = threading.Lock()

        self.reddit = praw.Reddit(
            client_id=os.environ['PRAW_CLIENT_ID'],
            client_secret=os.environ['PRAW_CLIENT_SECRET'],
            password=os.environ['REDDIT_PASSWORD'],
            redirect_uri=self.redirect_uri,
            user_agent=self.user_agent,
            username=os.environ['REDDIT_USERNAME'],
        )
        self.subreddit = self.reddit.subreddit(self.subreddit_name)  # "AskReddit" for faster testing of submission loop

        self.migrate_shelve()
        self.migrate_last_online()

    @staticmethod
    def validate_env() -> bool:
        required_env = [
            'DISCORD_REDDIT_CHANNEL_ID',
            'PRAW_CLIENT_ID',
            'PRAW_CLIENT_SECRET',
            'REDDIT_PASSWORD',
            'REDDIT_USERNAME',
        ]
        for env in required_env:
            if env not in os.environ:
                sys.stderr.write(f"Environment variable ``{env}`` must be defined\n")
                return False
        return True

    def migrate_last_online(self):
        if os.path.isfile(os.path.join(self.data_dir, 'last_online')):
            os.remove(os.path.join(self.data_dir, 'last_online'))

    def migrate_shelve(self):
        with self.lock, shelve.open(self.db) as db:
            if 'submissions' not in db and 'comments' not in db:
                db['comments'] = {}
                db['submissions'] = {}
                submissions = db['submissions']
                for k, v in db.items():
                    if k not in ['comments', 'submissions']:
                        submissions[k] = v
                        assert submissions[k] == v
                db['submissions'] = submissions
                keys_to_delete = [k for k in db if k not in ['comments', 'submissions']]
                for k in keys_to_delete:
                    del db[k]
                    assert k not in db

    def process_comment(self, comment: models.Comment):
        with self.lock, shelve.open(self.db) as db:
            comments = db.get('comments', {})
            if comment.id in comments and comments[comment.id].get('processed', False):
                return

            comments[comment.id] = {
                'author': str(comment.author),
                'body': comment.body,
                'created_utc': comment.created_utc,
                'processed': True,
                'slash_command': {'project': None, 'command': None},
            }
            # the shelve doesn't update unless we recreate the main key
            db['comments'] = comments

        self.slash_commands(comment=comment)

    def process_submission(self, submission: models.Submission):
        """
        Process a reddit submission.

        Parameters
        ----------
        submission : praw.models.Submission
            The submission to process.
        """
        with self.lock, shelve.open(self.db) as db:
            submissions = db.get('submissions', {})
            if submission.id not in submissions:
                submissions[submission.id] = {}
                submission_exists = False
            else:
                submission_exists = True

            # the shelve doesn't update unless we recreate the main key
            submissions[submission.id].update(vars(submission))
            db['submissions'] = submissions

        if not submission_exists:
            print(f'submission id: {submission.id}')
            print(f'submission title: {submission.title}')
            print('---------')
            if os.getenv('DISCORD_REDDIT_CHANNEL_ID'):
                self.discord(submission=submission)
            self.flair(submission=submission)
            self.karma(submission=submission)

    def discord(self, submission: models.Submission):
        """
        Send a discord message.

        Parameters
        ----------
        db : shelve.Shelf
            The database.
        submission : praw.models.Submission
            The submission to process.

        Returns
        -------
        shelve.Shelf
            The updated database.
        """
        # get the flair color
        try:
            color = int(submission.link_flair_background_color, 16)
        except Exception:
            color = int('ffffff', 16)

        try:
            redditor = self.reddit.redditor(name=submission.author)
        except Exception:
            return

        submission_time = datetime.fromtimestamp(submission.created_utc)

        # create the discord embed
        embed = discord.Embed(
            author=discord.EmbedAuthor(
                name=str(submission.author),
                url=f'https://www.reddit.com/user/{submission.author}',
                icon_url=str(redditor.icon_img),
            ),
            title=submission.title,
            url=submission.url,
            description=submission.selftext,
            color=color,
            thumbnail='https://www.redditstatic.com/desktop2x/img/snoo_discovery@1x.png',
            footer=discord.EmbedFooter(
                text=f'Posted on r/{self.subreddit_name} at {submission_time}',
                icon_url='https://www.redditstatic.com/desktop2x/img/favicon/favicon-32x32.png'
            )
        )

        # actually send the embed
        message = globals.DISCORD_BOT.send_message(
            channel_id=os.getenv("DISCORD_REDDIT_CHANNEL_ID"),
            embeds=[embed],
        )

        if message:
            with self.lock, shelve.open(self.db) as db:
                # the shelve doesn't update unless we recreate the main key
                submissions = db['submissions']
                submissions[submission.id]['bot_discord'] = {'sent': True, 'sent_utc': int(time.time())}
                db['submissions'] = submissions

    def flair(self, submission: models.Submission):
        # todo
        pass

    def karma(self, submission: models.Submission):
        # todo
        pass

    def slash_commands(self, comment: models.Comment):
        if comment.body.startswith("/"):
            print(f"Processing slash command: {comment.body}")
            # Split the comment into project and command
            parts = comment.body[1:].split()
            project = parts[0]
            command = parts[1] if len(parts) > 1 else None

            # Check if the command file exists in self.commands_dir
            command_file = os.path.join(self.commands_dir, project, f"{command}.md") if command else None
            if command_file and os.path.isfile(command_file):
                # Open the markdown file and read its contents
                with open(command_file, 'r', encoding='utf-8') as file:
                    file_contents = file.read()

                # Reply to the comment with the contents of the file
                comment.reply(file_contents)
            else:
                # Log error message
                print(f"Unknown command: {command} in project: {project}")
            with self.lock, shelve.open(self.db) as db:
                # the shelve doesn't update unless we recreate the main key
                comments = db['comments']
                comments[comment.id]['slash_command'] = {'project': project, 'command': command}
                db['comments'] = comments

    def _comment_loop(self, test: bool = False):
        # process comments and then keep monitoring
        for comment in self.subreddit.stream.comments():
            self.process_comment(comment=comment)
            if self.STOP_SIGNAL:
                break
            if test:
                return comment

    def _submission_loop(self, test: bool = False):
        # process submissions and then keep monitoring
        for submission in self.subreddit.stream.submissions():
            self.process_submission(submission=submission)
            if self.STOP_SIGNAL:
                break
            if test:
                return submission

    def start(self):
        # start comment and submission loops in separate threads
        self.comment_thread = threading.Thread(target=self._comment_loop, daemon=True)
        self.comment_thread.start()

        self.submission_thread = threading.Thread(target=self._submission_loop, daemon=True)
        self.submission_thread.start()

    def start_threaded(self):
        try:
            # Start the reddit bot in a separate thread
            self.bot_thread = threading.Thread(target=self.start, daemon=True)
            self.bot_thread.start()
        except KeyboardInterrupt:
            print("Keyboard Interrupt Detected")
            self.stop()

    def stop(self):
        print("Attempting to stop reddit bot")
        self.STOP_SIGNAL = True
        if self.bot_thread is not None and self.bot_thread.is_alive():
            self.comment_thread.join()
            self.submission_thread.join()
            self.bot_thread.join()
            print("Reddit bot stopped")
