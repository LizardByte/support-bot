# local imports
from src.common import sponsors


def test_get_github_sponsors(mocker):
    sponsor_data = {
        'data': {
            'organization': {
                'sponsorshipsAsMaintainer': {
                    'edges': [],
                },
            },
        },
    }
    response = mocker.Mock()
    response.json.return_value = sponsor_data
    post = mocker.patch('src.common.sponsors.requests.post', return_value=response)

    data = sponsors.get_github_sponsors()

    assert data
    assert 'errors' not in data
    assert 'data' in data
    assert 'organization' in data['data']
    assert 'sponsorshipsAsMaintainer' in data['data']['organization']
    assert 'edges' in data['data']['organization']['sponsorshipsAsMaintainer']
    post.assert_called_once()


def test_get_github_sponsors_error(no_github_token, mocker):
    response = mocker.Mock()
    response.json.return_value = {'message': 'Bad credentials'}
    mocker.patch('src.common.sponsors.requests.post', return_value=response)

    data = sponsors.get_github_sponsors()

    assert not data
