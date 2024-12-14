# local imports
from src.common import sponsors


def test_get_github_sponsors():
    data = sponsors.get_github_sponsors()
    assert data
    assert 'errors' not in data
    assert 'data' in data
    assert 'organization' in data['data']
    assert 'sponsorshipsAsMaintainer' in data['data']['organization']
    assert 'edges' in data['data']['organization']['sponsorshipsAsMaintainer']


def test_get_github_sponsors_error(no_github_token):
    data = sponsors.get_github_sponsors()
    assert not data
