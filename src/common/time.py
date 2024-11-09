# standard imports
import datetime


def iso_to_datetime(iso_str):
    """
    Convert an ISO 8601 string to a datetime object.

    Parameters
    ----------
    iso_str : str
        The ISO 8601 string to convert.

    Returns
    -------
    datetime.datetime
        The datetime object.
    """
    return datetime.datetime.fromisoformat(iso_str)
