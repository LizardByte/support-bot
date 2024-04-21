# standard imports
from typing import Union

# lib imports
import requests

# convert month number to igdb human-readable month
month_dictionary = {
    1: 'Jan',
    2: 'Feb',
    3: 'Mar',
    4: 'Apr',
    5: 'May',
    6: 'Jun',
    7: 'Jul',
    8: 'Aug',
    9: 'Sep',
    10: 'Oct',
    11: 'Nov',
    12: 'Dec'
}


def igdb_authorization(client_id: str, client_secret: str) -> dict:
    """
    Authorization for IGDB.

    Return an authorization dictionary for the IGDB api.

    Parameters
    ----------
    client_id : str
        IGDB/Twitch API client id.
    client_secret : str
        IGDB/Twitch client secret.

    Returns
    -------
    dict
        Authorization dictionary.
    """
    grant_type = 'client_credentials'

    auth_headers = {
        'Accept': 'application/json',
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': grant_type
    }

    token_url = 'https://id.twitch.tv/oauth2/token'

    authorization = post_json(url=token_url, headers=auth_headers)
    return authorization


def get_json(url: str) -> Union[dict, list]:
    """
    Make a GET request and get the response in json.

    Makes a GET request to the given url.

    Parameters
    ----------
    url : str
        The url for the GET request.

    Returns
    -------
    any
        The json response.
    """
    res = requests.get(url=url)
    data = res.json()

    return data


def post_json(url: str, headers: dict) -> Union[dict, list]:
    """
    Make a POST request and get response in json.

    Makes a POST request with given headers to the given url.

    Parameters
    ----------
    url : str
        The url for the POST request.
    headers : dict
        Headers for the POST request.

    Returns
    -------
    any
        The json response.
    """
    result = requests.post(url=url, data=headers).json()
    return result
