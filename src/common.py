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


# constants
avatar = get_bot_avatar(gravatar=os.environ['GRAVATAR_EMAIL'])
org_name = 'LizardByte'
bot_name = f'{org_name}-Bot'
bot_url = 'https://app.lizardbyte.dev'
