# standard imports
from io import BytesIO
import os

# lib imports
from libgravatar import Gravatar
import requests

# local imports
from src.common.version import __version__


colors = {
    'black': 0x000000,
    'green': 0x00ff00,
    'orange': 0xffa500,
    'purple': 0x9147ff,
    'red': 0xff0000,
    'white': 0xffffff,
    'yellow': 0xffff00,
}


def get_bot_avatar(gravatar: str) -> str:
    """
    Get Gravatar image url.

    Return the Gravatar image url of the given email address.

    Parameters
    ----------
    gravatar : str
        The Gravatar email address.

    Returns
    -------
    str
        Gravatar image url.
    """

    g = Gravatar(email=gravatar)
    image_url = g.get_image()

    return image_url


def get_avatar_bytes():
    avatar_response = requests.get(url=avatar)
    avatar_img = BytesIO(avatar_response.content).read()
    return avatar_img


def get_app_dirs():
    # parent directory name of this file, not full path
    parent_dir = os.path.dirname(os.path.abspath(__file__)).split(os.sep)[-3]
    if parent_dir == 'app':  # running in Docker container
        a = '/app'
        d = '/data'
    else:  # running locally
        a = os.getcwd()
        d = os.path.join(os.getcwd(), 'data')
    os.makedirs(d, exist_ok=True)
    return a, d


# constants
avatar = get_bot_avatar(gravatar=os.environ['GRAVATAR_EMAIL'])
org_name = 'LizardByte'
bot_name = f'{org_name}-Bot'
bot_url = 'https://app.lizardbyte.dev'
app_dir, data_dir = get_app_dirs()
version = __version__
