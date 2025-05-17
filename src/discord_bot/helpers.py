# standard imports
from typing import Any

# lib imports
import requests


def get_json(url: str) -> Any:
    """
    Make a GET request and get the response in json.

    Makes a GET request to the given url.

    Parameters
    ----------
    url : str
        The url for the GET request.

    Returns
    -------
    Any
        The json response.
    """
    res = requests.get(url=url)
    data = res.json()

    return data
