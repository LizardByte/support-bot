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
    if call.when == 'call' and call.excinfo is not None:
        # Test has failed
        excinfo = call.excinfo
        tb = excinfo._excinfo[2]  # Get the original traceback
        while tb is not None:
            frame = tb.tb_frame

            # Extract information from frame
            if 'self' in frame.f_locals:
                self_arg = frame.f_locals['self']
                if isinstance(self_arg, prawcore.requestor.Requestor):
                    if 'kwargs' in frame.f_locals:
                        kwargs_arg = frame.f_locals['kwargs']

                        # Redact auth values
                        if 'auth' in kwargs_arg and kwargs_arg['auth'] is not None:
                            kwargs_arg['auth'] = ('*' * len(kwargs_arg['auth'][0]), '*' * len(kwargs_arg['auth'][1]))

                        # Redact token values
                        if 'data' in kwargs_arg and kwargs_arg['data'] is not None:
                            for i, (key, value) in enumerate(kwargs_arg['data']):
                                if key in token_types:
                                    kwargs_arg['data'][i] = (key, '*' * len(value))

                if isinstance(self_arg, prawcore.auth.TrustedAuthenticator):
                    if 'data' in frame.f_locals:
                        for k, v in frame.f_locals['data'].items():
                            if k in token_types:
                                frame.f_locals['data'][k] = '*' * len(v)
            tb = tb.tb_next
