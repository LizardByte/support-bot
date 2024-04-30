# standard imports
from datetime import datetime
import os
import requests
import shelve
import sys
import threading
import time
from typing import Optional

# lib imports
import praw
from praw import models

# local imports
from src import common


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

        if not kwargs.get('redirect_uri', None):
            try:  # for running in replit
                self.redirect_uri = f'https://{os.environ["REPL_SLUG"]}.{os.environ["REPL_OWNER"].lower()}.repl.co'
            except KeyError:
                self.redirect_uri = os.getenv('REDIRECT_URI', 'http://localhost:8080')
        else:
            self.redirect_uri = kwargs['redirect_uri']

        # directories
        self.data_dir = common.data_dir

        self.last_online_file = os.path.join(self.data_dir, 'last_online')
        self.reddit = praw.Reddit(
            client_id=os.environ['PRAW_CLIENT_ID'],
            client_secret=os.environ['PRAW_CLIENT_SECRET'],
            password=os.environ['REDDIT_PASSWORD'],
            redirect_uri=self.redirect_uri,
            user_agent=self.user_agent,
            username=os.environ['REDDIT_USERNAME'],
        )
        self.subreddit = self.reddit.subreddit(self.subreddit_name)  # "AskReddit" for faster testing of submission loop

    @staticmethod
    def validate_env() -> bool:
        required_env = [
            'DISCORD_WEBHOOK',
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

    def process_comment(self, comment: models.Comment):
        # todo
        pass

    def process_submission(self, submission: models.Submission):
        """
        Process a reddit submission.

        Parameters
        ----------
        submission : praw.models.Submission
            The submission to process.
        """
        last_online = self.get_last_online()

        if last_online < submission.created_utc:
            print(f'submission id: {submission.id}')
            print(f'submission title: {submission.title}')
            print('---------')

            with shelve.open(os.path.join(self.data_dir, 'reddit_bot_database')) as db:
                try:
                    db[submission.id]
                except KeyError:
                    submission_exists = False
                    db[submission.id] = vars(submission)
                else:
                    submission_exists = True

                if submission_exists:
                    for k, v in vars(submission).items():  # update the database with current values
                        try:
                            if db[submission.id][k] != v:
                                db[submission.id][k] = v
                        except KeyError:
                            db[submission.id][k] = v

                else:
                    try:
                        os.environ['DISCORD_WEBHOOK']
                    except KeyError:
                        pass
                    else:
                        db = self.discord(db=db, submission=submission)
                    db = self.flair(db=db, submission=submission)
                    db = self.karma(db=db, submission=submission)

        # re-write the last online time
        self.last_online_writer()

    def discord(self, db: shelve.Shelf, submission: models.Submission) -> Optional[shelve.Shelf]:
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

        # create the discord message
        # todo: use the running discord bot, directly instead of using a webhook
        discord_webhook = {
            'username': 'LizardByte-Bot',
            'avatar_url': self.avatar,
            'embeds': [
                {
                    'author': {
                        'name': str(submission.author),
                        'url': f'https://www.reddit.com/user/{submission.author}',
                        'icon_url': str(redditor.icon_img)
                    },
                    'title': str(submission.title),
                    'url': str(submission.url),
                    'description': str(submission.selftext),
                    'color': color,
                    'thumbnail': {
                        'url': 'https://www.redditstatic.com/desktop2x/img/snoo_discovery@1x.png'
                    },
                    'footer': {
                        'text': f'Posted on r/{self.subreddit_name} at {submission_time}',
                        'icon_url': 'https://www.redditstatic.com/desktop2x/img/favicon/favicon-32x32.png'
                    }
                }
            ]
        }

        # actually send the message
        r = requests.post(os.environ['DISCORD_WEBHOOK'], json=discord_webhook)

        if r.status_code == 204:  # successful completion of request, no additional content
            # update the database
            db[submission.id]['bot_discord'] = {'sent': True, 'sent_utc': int(time.time())}

        return db

    def flair(self, db: shelve.Shelf, submission: models.Submission) -> shelve.Shelf:
        # todo
        return db

    def karma(self, db: shelve.Shelf, submission: models.Submission) -> shelve.Shelf:
        # todo
        return db

    def commands(self, db: shelve.Shelf, submission: models.Submission) -> shelve.Shelf:
        # todo
        return db

    def last_online_writer(self) -> int:
        """
        Write the current time to the last online file.

        Returns
        -------
        int
            The current time.
        """
        last_online = int(time.time())
        with open(self.last_online_file, 'w') as f:
            f.write(str(last_online))

        return last_online

    def get_last_online(self) -> int:
        """
        Get the last online time.

        Returns
        -------
        int
            The last online time.
        """
        try:
            with open(self.last_online_file, 'r') as f:
                last_online = int(f.read())
        except FileNotFoundError:
            last_online = self.last_online_writer()

        return last_online

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
