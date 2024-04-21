# lib imports
from libgravatar import Gravatar


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
