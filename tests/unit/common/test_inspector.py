# local imports
from src.common import inspector


def test_current_name():
    assert inspector.current_name() == 'test_current_name'
