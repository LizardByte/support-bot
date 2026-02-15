# standard imports
from datetime import datetime
import os
import sys
import threading
import time
from typing import Optional

# lib imports
import discord
import praw
from praw import models
import prawcore

# local imports
from src.common import common
from src.common import globals
from src.common import inspector
from src.common.database import Database
from src.common.rank import RankSystem


class Bot:
    def __init__(self, **kwargs):
        self.STOP_SIGNAL = False
        self.DEGRADED = False
        self.DEGRADED_REASONS = []

        # threads
        self.bot_thread = threading.Thread(target=lambda: None)
        self.comment_thread = threading.Thread(target=lambda: None)
        self.submission_thread = threading.Thread(target=lambda: None)

        # ensure we have all required environment variables
        self.env_valid = self.validate_env()

        self.version = kwargs.get('version', 'v1')
        self.user_agent = kwargs.get(
            'user_agent',
            f'praw:dev.lizardbyte.app.support-bot:{self.version} (by /u/{os.getenv("REDDIT_USERNAME")})')
        self.avatar = kwargs.get('avatar', common.get_bot_avatar(gravatar=os.environ['GRAVATAR_EMAIL']))
        self.subreddit_name = kwargs.get('subreddit', os.getenv('PRAW_SUBREDDIT', 'LizardByte'))
        self.redirect_uri = kwargs.get('redirect_uri', os.getenv('REDIRECT_URI', 'http://localhost:8080'))

        # directories
        self.data_dir = common.data_dir
        self.commands_dir = os.path.join(self.data_dir, "support-bot-commands", "docs")

        # database
        self.db = Database(db_name='reddit_bot_database')

        # initialize database tables if they don't exist
        with self.db as db:
            if not db.tables():
                db.table('comments')
                db.table('submissions')

        # Create rank system instance directly
        self.rank_system = RankSystem(
            bot=self,
            xp_range=(150, 250),  # use a higher XP because reddit is not nearly as active as discord
        )

        self.reddit = praw.Reddit(
            client_id=os.environ['PRAW_CLIENT_ID'],
            client_secret=os.environ['PRAW_CLIENT_SECRET'],
            password=os.environ['REDDIT_PASSWORD'],
            redirect_uri=self.redirect_uri,
            user_agent=self.user_agent,
            username=os.environ['REDDIT_USERNAME'],
        )
        self.subreddit = self.reddit.subreddit(self.subreddit_name)  # "AskReddit" for faster testing of submission loop

        # Run Reddit rank migration on startup
        self.migrate_reddit_ranks()

    def validate_env(self) -> bool:
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
                self.DEGRADED = True
                reason = inspector.current_name()
                self.DEGRADED_REASONS.append(reason) if reason not in self.DEGRADED_REASONS else None
                return False
        return True

    def fetch_user(self, name: str) -> Optional[models.Redditor]:
        """
        Get a Redditor object by username.

        Parameters
        ----------
        name : str
            The Reddit username.

        Returns
        -------
        praw.models.Redditor
            The Redditor object.
        """
        redditor = self.reddit.redditor(name=name)

        try:
            # praw does not actually get the user object until you access it
            redditor.id
        except prawcore.NotFound:
            # If the user is suspended or deleted, return None
            print(f"User {name} not found or suspended.")
            return None

        return redditor

    def process_comment(self, comment: models.Comment):
        with self.db as db:
            q = self.db.query()
            comments_table = db.table('comments')
            existing_comment = comments_table.get(q.reddit_id == comment.id)

            if existing_comment and existing_comment.get('processed', False):
                return

        comment_data = {
            'reddit_id': comment.id,  # Store Reddit ID as a regular field
            'author': str(comment.author),
            'body': comment.body,
            'created_utc': comment.created_utc,
            'processed': False,
            'slash_command': {'project': None, 'command': None},
        }

        # Award XP for the comment if it's from a valid user
        try:
            if comment.author:
                # Pass the actual Reddit user object to award_xp
                xp_result = self.award_reddit_xp(comment.author)
                if xp_result and xp_result.get('level_up'):
                    print(f"User {comment.author.name} leveled up to {xp_result.get('level')}!")
        except Exception as e:
            print(f"Error awarding XP: {e}")

        comment_data = self.slash_commands(comment=comment, comment_data=comment_data)
        comment_data['processed'] = True

        with self.db as db:
            q = self.db.query()
            comments_table = db.table('comments')
            if existing_comment:
                comments_table.update(comment_data, q.reddit_id == comment.id)
            else:
                comments_table.insert(comment_data)

    def process_submission(self, submission: models.Submission):
        """
        Process a reddit submission.

        Parameters
        ----------
        submission : praw.models.Submission
            The submission to process.
        """
        with self.db as db:
            q = self.db.query()
            submissions_table = db.table('submissions')
            existing_submission = submissions_table.get(q.reddit_id == submission.id)

            if existing_submission:
                # Extract submission data to store
                submission_data = {
                    'reddit_id': submission.id,  # Store Reddit ID as a regular field
                    'title': submission.title,
                    'selftext': submission.selftext,
                    'author': str(submission.author),
                    'created_utc': submission.created_utc,
                    'permalink': submission.permalink,
                    'url': submission.url,
                    'link_flair_text': submission.link_flair_text if hasattr(submission, 'link_flair_text') else None,
                    'link_flair_background_color': submission.link_flair_background_color if hasattr(
                        submission, 'link_flair_background_color') else None,
                    'bot_discord': existing_submission.get(
                        'bot_discord', {'sent': False, 'sent_utc': None}),
                }
                submissions_table.update(submission_data, q.reddit_id == submission.id)
                return

        # Extract submission data to store
        submission_data = {
            'reddit_id': submission.id,  # Store Reddit ID as a regular field
            'title': submission.title,
            'selftext': submission.selftext,
            'author': str(submission.author),
            'created_utc': submission.created_utc,
            'permalink': submission.permalink,
            'url': submission.url,
            'link_flair_text': submission.link_flair_text if hasattr(submission, 'link_flair_text') else None,
            'link_flair_background_color': submission.link_flair_background_color if hasattr(
                submission, 'link_flair_background_color') else None,
            'bot_discord': {'sent': False, 'sent_utc': None},
        }

        print(f'submission id: {submission.id}')
        print(f'submission title: {submission.title}')
        print('---------')

        # Award XP for new submissions
        try:
            if submission.author:
                # Pass the actual Reddit user object
                xp_result = self.award_reddit_xp(submission.author)
                if xp_result and xp_result.get('level_up'):
                    print(f"User {submission.author.name} leveled up to {xp_result.get('level')}!")
        except Exception as e:
            print(f"Error awarding XP: {e}")

        if os.getenv('DISCORD_REDDIT_CHANNEL_ID'):
            submission_data = self.discord(submission=submission, submission_data=submission_data)
        submission_data = self.flair(submission=submission, submission_data=submission_data)
        submission_data = self.karma(submission=submission, submission_data=submission_data)

        with self.db as db:
            submissions_table = db.table('submissions')
            submissions_table.insert(submission_data)

    def award_reddit_xp(self, user: models.Redditor):
        """
        Award XP to a Reddit user.

        Parameters
        ----------
        user : praw.models.Redditor
            The Reddit user to award XP to.

        Returns
        -------
        dict or None
            XP award result or None if on cooldown
        """
        # Set the subreddit_id as a property on the user object for the rank system
        # This is a hack since Reddit user objects don't have subreddit_id by default
        user.subreddit_id = self.subreddit.id

        return self.rank_system.award_xp(
            platform='reddit',
            user=user,
        )

    def migrate_reddit_ranks(self):
        """
        Migrate existing Reddit data to the rank system.
        This will grant points for all existing submissions and comments.
        """
        try:
            # Check if migration has already been performed
            migration_status = self.rank_system.get_migration_status(
                platform='reddit',
                community_id=self.subreddit.id,
                source_id='reddit_bot_database',
            )

            if migration_status:
                print(f"Reddit ranks migration already completed on {migration_status.get('timestamp')}")
                return

            print("Starting Reddit ranks migration...")

            # Start the migration process
            stats = self.rank_system.migrate_from_reddit_database(
                reddit_bot=self,
                reddit_db=self.db,
                community_id=self.subreddit.id,
            )

            # Record the migration as completed
            self.rank_system.set_migration_completed(
                platform='reddit',
                community_id=self.subreddit.id,
                source_id='reddit_bot_database',
                stats=stats,
            )

            print(f"Reddit ranks migration completed: {stats}")

        except Exception as e:
            print(f"Error during Reddit ranks migration: {e}")
            self.DEGRADED = True
            reason = inspector.current_name()
            self.DEGRADED_REASONS.append(reason) if reason not in self.DEGRADED_REASONS else None

    def discord(self, submission: models.Submission, submission_data: dict) -> dict:
        """
        Send a discord message.

        Parameters
        ----------
        submission : praw.models.Submission
            The submission to process.
        submission_data : dict
            The submission data to process.
        """
        # get the flair color
        try:
            color = int(submission.link_flair_background_color, 16)
        except Exception:
            color = common.colors['white']

        try:
            redditor = self.fetch_user(name=submission.author)
        except Exception:
            self.DEGRADED = True
            reason = inspector.current_name()
            self.DEGRADED_REASONS.append(reason) if reason not in self.DEGRADED_REASONS else None
            return submission_data

        # create the discord embed
        embed = discord.Embed(
            author=discord.EmbedAuthor(
                name=str(redditor.name),
                url=f'https://www.reddit.com/user/{redditor.name}',
                icon_url=str(redditor.icon_img),
            ),
            color=color,
            description=submission.selftext,
            footer=discord.EmbedFooter(
                text=f'Posted on r/{self.subreddit_name}',
                icon_url='https://www.redditstatic.com/desktop2x/img/favicon/favicon-32x32.png'
            ),
            title=submission.title,
            url=f"https://www.reddit.com{submission.permalink}",
            timestamp=datetime.fromtimestamp(submission.created_utc),
            thumbnail='https://www.redditstatic.com/desktop2x/img/snoo_discovery@1x.png',
        )

        # actually send the embed
        message = globals.DISCORD_BOT.send_message(
            channel_id=os.getenv("DISCORD_REDDIT_CHANNEL_ID"),
            embed=embed,
        )

        if message:
            submission_data['bot_discord'] = {
                'sent': True,
                'sent_utc': int(time.time()),
            }

        return submission_data

    def flair(self, submission: models.Submission, submission_data: dict) -> dict:
        # todo
        return submission_data

    def karma(self, submission: models.Submission, submission_data: dict) -> dict:
        # todo
        return submission_data

    def slash_commands(self, comment: models.Comment, comment_data: dict) -> dict:
        if not comment.body.startswith("/"):
            return comment_data

        print(f"Processing slash command: {comment.body}")
        # Split the comment into project and command
        parts = comment.body[1:].split()
        project = parts[0]
        command = parts[1] if len(parts) > 1 else None

        # Check if the command file exists in self.commands_dir
        command_file = os.path.join(self.commands_dir, project, f"{command}.md") if command else None

        if not command_file or not os.path.isfile(command_file):
            return comment_data

        # Open the markdown file and read its contents
        with open(command_file, 'r', encoding='utf-8') as file:
            file_contents = file.read()

        # Reply to the comment with the contents of the file
        comment.reply(file_contents)

        comment_data['slash_command'] = {
            'project': project,
            'command': command,
        }

        return comment_data

    def _comment_loop(self, test: bool = False):
        # process comments and then keep monitoring
        reason = inspector.current_name()
        while True:
            if self.STOP_SIGNAL:
                break

            if self.DEGRADED and reason in self.DEGRADED_REASONS and len(self.DEGRADED_REASONS) == 1:
                self.DEGRADED = False

            try:
                for comment in self.subreddit.stream.comments():
                    self.process_comment(comment=comment)
                    if self.STOP_SIGNAL:
                        break
                    if test:
                        return comment
            except prawcore.exceptions.ServerError as e:
                print(f"Server Error: {e}")
                self.DEGRADED = True
                self.DEGRADED_REASONS.append(reason) if reason not in self.DEGRADED_REASONS else None
                time.sleep(60)

    def _submission_loop(self, test: bool = False):
        # process submissions and then keep monitoring
        reason = inspector.current_name()
        while True:
            if self.STOP_SIGNAL:
                break

            if self.DEGRADED and reason in self.DEGRADED_REASONS and len(self.DEGRADED_REASONS) == 1:
                self.DEGRADED = False

            try:
                for submission in self.subreddit.stream.submissions():
                    self.process_submission(submission=submission)
                    if self.STOP_SIGNAL:
                        break
                    if test:
                        return submission
            except prawcore.exceptions.ServerError as e:
                print(f"Server Error: {e}")
                self.DEGRADED = True
                self.DEGRADED_REASONS.append(reason) if reason not in self.DEGRADED_REASONS else None
                time.sleep(60)

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
            self.DEGRADED = True
            reason = inspector.current_name()
            self.DEGRADED_REASONS.append(reason) if reason not in self.DEGRADED_REASONS else None
            self.stop()

    def stop(self):
        print("Attempting to stop reddit bot")
        self.STOP_SIGNAL = True
        self.DEGRADED = True
        reason = inspector.current_name()
        self.DEGRADED_REASONS.append(reason) if reason not in self.DEGRADED_REASONS else None
        if self.bot_thread is not None and self.bot_thread.is_alive():
            self.comment_thread.join()
            self.submission_thread.join()
            self.bot_thread.join()
            print("Reddit bot stopped")
