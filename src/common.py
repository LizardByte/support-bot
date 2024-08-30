# standard imports
from io import BytesIO
import os

# lib imports
from libgravatar import Gravatar
import requests


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


def get_data_dir():
    # parent directory name of this file, not full path
    parent_dir = os.path.dirname(os.path.abspath(__file__)).split(os.sep)[-2]
    if parent_dir == 'app':  # running in Docker container
        d = '/data'
    else:  # running locally
        d = os.path.join(os.getcwd(), 'data')
    os.makedirs(d, exist_ok=True)
    return d


# constants
avatar = get_bot_avatar(gravatar=os.environ['GRAVATAR_EMAIL'])
org_name = 'LizardByte'
bot_name = f'{org_name}-Bot'
bot_url = 'https://app.lizardbyte.dev'
data_dir = get_data_dir()
version = '0.0.0'
