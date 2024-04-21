# standard imports
from datetime import datetime
import os
import random
import requests
import shelve
import socket
import sys
import threading
import time
from typing import Optional

# lib imports
from libgravatar import Gravatar
import praw
from praw import models
from praw.util.token_manager import FileTokenManager

# modify as required
APP = 'lizardbyte-bot'
VERSION = 'v1'
REDDIT_USER = 'ReenigneArcher'
USER_AGENT = f'{APP}/{VERSION} by u/{REDDIT_USER}'

try:  # for running in replit
    redirect_uri = f'https://{os.environ["REPL_SLUG"]}.{os.environ["REPL_OWNER"].lower()}.repl.co'
except KeyError:
    redirect_uri = os.environ['REDIRECT_URI']

# globals
avatar = None
reddit: Optional[praw.Reddit] = None
bot_thread = threading.Thread(target=lambda: None)
STOP_SIGNAL = False

# directories
# parent directory name of this file, not full path
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).split(os.sep)[-1]
print(f'PARENT_DIR: {PARENT_DIR}')
if PARENT_DIR == 'app':
    # running in Docker container
    DATA_DIR = '/data'
else:
    # running locally
    DATA_DIR = os.path.join(os.getcwd(), 'data')
print(F'DATA_DIR: {DATA_DIR}')
os.makedirs(DATA_DIR, exist_ok=True)

REFRESH_TOKEN_FILE = os.path.join(DATA_DIR, 'refresh_token')
LAST_ONLINE_FILE = os.path.join(DATA_DIR, 'last_online')


def initialize_refresh_token_file():
    if os.path.isfile(REFRESH_TOKEN_FILE):
        return True

    # https://www.reddit.com/api/v1/scopes.json
    scopes = [
        'read',  # Access posts and comments through my account.
    ]

    reddit_auth = praw.Reddit(
        client_id=os.environ['PRAW_CLIENT_ID'],
        client_secret=os.environ['PRAW_CLIENT_SECRET'],
        redirect_uri=redirect_uri,
        user_agent=USER_AGENT,
    )

    state = str(random.randint(0, 65000))
    url = reddit_auth.auth.url(scopes=scopes, state=state, duration="permanent")
    print(f"Now open this url in your browser: {url}")

    client, data = receive_connection()
    param_tokens = data.split(" ", 2)[1].split("?", 1)[1].split("&")
    params = {
        key: value for (key, value) in [token.split("=") for token in param_tokens]
    }

    if state != params["state"]:
        send_message(
            client,
            f"State mismatch. Expected: {state} Received: {params['state']}",
        )
        return False
    elif "error" in params:
        send_message(client, params["error"])
        return False

    refresh_token = reddit_auth.auth.authorize(params["code"])
    with open(REFRESH_TOKEN_FILE, 'w+') as f:
        f.write(refresh_token)

    send_message(client, f"Refresh token: {refresh_token}")
    print('Refresh token has been written to "refresh_token" file')
    return True


def receive_connection() -> tuple[socket.socket, str]:
    """
    Wait for and then return a connected socket.

    Opens a TCP connection on port 8080, and waits for a single client.

    Returns
    -------
    tuple[socket.socket, str]
        The connected socket and the data received.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', 8080))
    server.listen()
    # Handle one request from the client
    while True:
        (clientSocket, clientAddress) = server.accept()
        data = clientSocket.recv(1024)

        if data != b'':
            # Wait until we receive the data from reddit
            if data.startswith(b'GET /?state='):
                # Send back what you received
                clientSocket.send(data)

                break
    server.close()
    return clientSocket, data.decode("utf-8")


def send_message(client: socket.socket, message: str):
    """
    Send a message to the client and close the connection.

    Parameters
    ----------
    client : socket.socket
        The client socket.
    message : str
        The message to send.
    """
    print(f'message: {message}')
    client.send(f"HTTP/1.1 200 OK\r\n\r\n{message}".encode("utf-8"))
    client.close()


def get_bot_avatar(gravatar: str) -> str:
    """
    Get the gravatar of a given email.

    Parameters
    ----------
    gravatar : str
        The gravatar email.

    Returns
    -------
    str
        The gravatar image url.
    """

    g = Gravatar(email=gravatar)
    image_url = g.get_image()

    return image_url


def process_submission(submission: models.Submission):
    """
    Process a reddit submission.

    Parameters
    ----------
    submission : praw.models.Submission
        The submission to process.
    """
    last_online = get_last_online()

    if last_online < submission.created_utc:
        print(f'submission id: {submission.id}')
        print(f'submission title: {submission.title}')
        print('---------')

        with shelve.open(os.path.join(DATA_DIR, 'reddit_bot_database')) as db:
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
                    db = discord(db=db, submission=submission)
                db = flair(db=db, submission=submission)
                db = karma(db=db, submission=submission)

    # re-write the last online time
    last_online_writer()


def discord(db: shelve.Shelf, submission: models.Submission) -> Optional[shelve.Shelf]:
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
        redditor = reddit.redditor(name=submission.author)
    except Exception:
        return

    submission_time = datetime.fromtimestamp(submission.created_utc)

    # create the discord message
    # todo: use the running discord bot, directly instead of using a webhook
    discord_webhook = {
        'username': 'LizardByte-Bot',
        'avatar_url': avatar,
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
                    'text': f'Posted on r/{os.environ["PRAW_SUBREDDIT"]} at {submission_time}',
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


def flair(db: shelve.Shelf, submission: models.Submission) -> shelve.Shelf:
    # todo
    return db


def karma(db: shelve.Shelf, submission: models.Submission) -> shelve.Shelf:
    # todo
    return db


def commands(db: shelve.Shelf, submission: models.Submission) -> shelve.Shelf:
    # todo
    return db


def last_online_writer() -> int:
    """
    Write the current time to the last online file.

    Returns
    -------
    int
        The current time.
    """
    last_online = int(time.time())
    with open(LAST_ONLINE_FILE, 'w') as f:
        f.write(str(last_online))

    return last_online


def get_last_online() -> int:
    """
    Get the last online time.

    Returns
    -------
    int
        The last online time.
    """
    try:
        with open(LAST_ONLINE_FILE, 'r') as f:
            last_online = int(f.read())
    except FileNotFoundError:
        last_online = last_online_writer()

    return last_online


def init():
    required_env = [
        'DISCORD_WEBHOOK',
        'PRAW_CLIENT_ID',
        'PRAW_CLIENT_SECRET',
        'PRAW_SUBREDDIT',
        'REDIRECT_URI'
    ]
    for env in required_env:
        if env not in os.environ:
            if env == 'REDIRECT_URI':
                try:
                    os.environ["REPL_SLUG"]
                except KeyError:
                    sys.stderr.write(f"Environment variable ``{env}`` must be defined\n")
            else:
                sys.stderr.write(f"Environment variable ``{env}`` must be defined\n")
            return False

    # avatar
    global avatar
    avatar = get_bot_avatar(gravatar=os.environ['GRAVATAR_EMAIL'])

    # verify reddit refresh token or get new
    token = initialize_refresh_token_file()

    if not token:
        sys.exit(1)

    refresh_token_manager = FileTokenManager(REFRESH_TOKEN_FILE)

    global reddit
    reddit = praw.Reddit(
        client_id=os.environ['PRAW_CLIENT_ID'],
        client_secret=os.environ['PRAW_CLIENT_SECRET'],
        token_manager=refresh_token_manager,
        user_agent=USER_AGENT,
    )

    subreddit = reddit.subreddit(os.environ['PRAW_SUBREDDIT'])  # use "AskReddit" for testing

    # process submissions and then keep monitoring
    for submission in subreddit.stream.submissions():
        process_submission(submission=submission)
        if STOP_SIGNAL:
            break


def start():
    global bot_thread
    try:
        # Start the reddit bot in a separate thread
        bot_thread = threading.Thread(target=init, daemon=True)
        bot_thread.start()
    except KeyboardInterrupt:
        print("Keyboard Interrupt Detected")
        stop()


def stop():
    print("Attempting to stop reddit bot")
    if bot_thread is not None and bot_thread.is_alive():
        print("Reddit bot stopped")
