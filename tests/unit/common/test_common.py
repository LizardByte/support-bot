# standard imports
import os
import re

# lib imports
import pytest

# local imports
from src.common import common


@pytest.fixture(scope='module')
def github_email():
    return 'octocat@github.com'


def test_colors():
    for color in common.colors.values():
        assert 0x000000 <= color <= 0xFFFFFF, f"{color} is not a valid hex color"


def test_get_bot_avatar(github_email):
    url = common.get_bot_avatar(gravatar=github_email)
    print(url)
    assert url.startswith('https://www.gravatar.com/avatar/')


def test_get_avatar_bytes(github_email, mocker):
    mocker.patch('src.common.common.avatar', common.get_bot_avatar(gravatar=github_email))
    avatar_bytes = common.get_avatar_bytes()
    assert avatar_bytes
    assert isinstance(avatar_bytes, bytes)


def test_get_app_dirs():
    app_dir, data_dir = common.get_app_dirs()
    assert app_dir
    assert data_dir
    assert os.path.exists(app_dir)
    assert os.path.exists(data_dir)
    assert os.path.isdir(app_dir)
    assert os.path.isdir(data_dir)
    assert app_dir == (os.getcwd() or '/app')
    assert data_dir == (os.path.join(os.getcwd(), 'data') or '/data')


def test_version():
    assert common.version
    assert isinstance(common.version, str)
    assert re.match(r'^\d+\.\d+\.\d+$', common.version)
