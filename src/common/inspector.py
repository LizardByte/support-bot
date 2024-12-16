# standard imports
import inspect


def current_name() -> str:
    """
    Get the name of the function that called this function

    Returns
    -------
    str
       the name of the function that called this function
    """
    return inspect.currentframe().f_back.f_code.co_name
