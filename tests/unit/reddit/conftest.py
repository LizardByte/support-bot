# lib imports
import prawcore
import pytest

token_types = [
    'access_token',
    'password',
    'refresh_token',
    'username',
]


def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """
    Intercept test failures and redact sensitive information from the requestor object.

    Parameters
    ----------
    item : pytest.Item
    call : pytest.CallInfo
    """
    if call.when != 'call' or call.excinfo is None:
        return

    _redact_traceback(call.excinfo._excinfo[2])


def _redact_traceback(tb):
    while tb is not None:
        _redact_frame_locals(frame_locals=tb.tb_frame.f_locals)
        tb = tb.tb_next


def _redact_frame_locals(frame_locals: dict):
    self_arg = frame_locals.get('self')

    if isinstance(self_arg, prawcore.requestor.Requestor):
        _redact_requestor_kwargs(kwargs_arg=frame_locals.get('kwargs'))

    if isinstance(self_arg, prawcore.auth.TrustedAuthenticator):
        _redact_token_mapping(data=frame_locals.get('data'))


def _redact_requestor_kwargs(kwargs_arg: dict | None):
    if not kwargs_arg:
        return

    _redact_auth(kwargs_arg=kwargs_arg)
    _redact_token_pairs(data=kwargs_arg.get('data'))


def _redact_auth(kwargs_arg: dict):
    auth = kwargs_arg.get('auth')
    if auth is not None:
        kwargs_arg['auth'] = ('*' * len(auth[0]), '*' * len(auth[1]))


def _redact_token_pairs(data: list | None):
    if data is None:
        return

    for i, (key, value) in enumerate(data):
        if key in token_types:
            data[i] = (key, '*' * len(value))


def _redact_token_mapping(data: dict | None):
    if data is None:
        return

    for key, value in data.items():
        if key in token_types:
            data[key] = '*' * len(value)
