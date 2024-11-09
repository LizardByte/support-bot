# standard imports
import os

# lib imports
import pytest

# local imports
from src.common import webapp


@pytest.fixture(scope='function')
def test_client():
    """Create a test client for testing webapp endpoints"""
    app = webapp.app
    app.testing = True

    client = app.test_client()

    # Create a test client using the Flask application configured for testing
    with client as test_client:
        # Establish an application context
        with app.app_context():
            yield test_client  # this is where the testing happens!


def test_status(test_client):
    """
    WHEN the '/status' page is requested (GET)
    THEN check that the response is valid
    """
    response = test_client.get('/status')
    assert response.status_code == 200


def test_favicon(test_client):
    """
    WHEN the '/favicon.ico' file is requested (GET)
    THEN check that the response is valid
    THEN check the content type is 'image/vnd.microsoft.icon'
    """
    response = test_client.get('/favicon.ico')
    assert response.status_code == 200
    assert response.content_type == 'image/vnd.microsoft.icon'


def test_discord_callback_invalid_state(discord_bot, test_client, mocker):
    """
    WHEN the '/discord/callback' endpoint is requested (GET) with an invalid state
    THEN check that the response is 'Invalid state'
    """
    mocker.patch('src.common.webapp.OAuth2Session.fetch_token', return_value={'access_token': 'fake_token'})
    mocker.patch('src.common.webapp.OAuth2Session.get', return_value=mocker.Mock(json=lambda: {'id': 'invalid_user'}))

    response = test_client.get('/discord/callback')
    assert response.data == b'Invalid state'
    assert response.status_code == 200


def test_webhook_invalid_source(test_client):
    """
    WHEN the '/webhook/<source>/<key>' endpoint is requested (POST) with an invalid source
    THEN check that the response is 'Invalid source'
    """
    response = test_client.post('/webhook/invalid_source/invalid_key')
    assert response.json == {"status": "error", "message": "Invalid source"}
    assert response.status_code == 400


def test_webhook_invalid_key(test_client, mocker):
    """
    WHEN the '/webhook/<source>/<key>' endpoint is requested (POST) with an invalid key
    THEN check that the response is 'Invalid key'
    """
    mocker.patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET_KEY": "valid_key"})
    response = test_client.post('/webhook/github_sponsors/invalid_key')
    assert response.json == {"status": "error", "message": "Invalid key"}
    assert response.status_code == 400


def test_webhook_github_sponsors(discord_bot, test_client, mocker):
    """
    WHEN the '/webhook/github_sponsors/<key>' endpoint is requested (POST) with valid data
    THEN check that the response is 'success'
    """
    mocker.patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET_KEY": "valid_key"})
    data = {
        'action': 'created',
        'sponsorship': {
            'sponsor': {
                'login': 'octocat',
                'url': 'https://github.com/octocat',
                'avatar_url': 'https://avatars.githubusercontent.com/u/583231',
            },
            'created_at': '1970-01-01T00:00:00Z',
        },
    }
    response = test_client.post('/webhook/github_sponsors/valid_key', json=data)
    assert response.json == {"status": "success"}
    assert response.status_code == 200


@pytest.mark.parametrize("data", [
    # https://support.atlassian.com/statuspage/docs/enable-webhook-notifications/
    {
        "meta": {
            "unsubscribe": "http://statustest.flyingkleinbrothers.com:5000/?unsubscribe=j0vqr9kl3513",
            "documentation": "http://doers.statuspage.io/customer-notifications/webhooks/",
        },
        "page": {
            "id": "j2mfxwj97wnj",
            "status_indicator": "major",
            "status_description": "Partial System Outage",
        },
        "component_update": {
            "created_at": "2013-05-29T21:32:28Z",
            "new_status": "operational",
            "old_status": "major_outage",
            "id": "k7730b5v92bv",
            "component_id": "rb5wq1dczvbm",
        },
        "component": {
            "created_at": "2013-05-29T21:32:28Z",
            "id": "rb5wq1dczvbm",
            "name": "Some Component",
            "status": "operational",
        },
    },
    {
        "meta": {
            "unsubscribe": "http://statustest.flyingkleinbrothers.com:5000/?unsubscribe=j0vqr9kl3513",
            "documentation": "http://doers.statuspage.io/customer-notifications/webhooks/",
        },
        "page": {
            "id": "j2mfxwj97wnj",
            "status_indicator": "critical",
            "status_description": "Major System Outage",
        },
        "incident": {
            "backfilled": False,
            "created_at": "2013-05-29T15:08:51-06:00",
            "impact": "critical",
            "impact_override": None,
            "monitoring_at": "2013-05-29T16:07:53-06:00",
            "postmortem_body": None,
            "postmortem_body_last_updated_at": None,
            "postmortem_ignored": False,
            "postmortem_notified_subscribers": False,
            "postmortem_notified_twitter": False,
            "postmortem_published_at": None,
            "resolved_at": None,
            "scheduled_auto_transition": False,
            "scheduled_for": None,
            "scheduled_remind_prior": False,
            "scheduled_reminded_at": None,
            "scheduled_until": None,
            "shortlink": "http://j.mp/18zyDQx",
            "status": "monitoring",
            "updated_at": "2013-05-29T16:30:35-06:00",
            "id": "lbkhbwn21v5q",
            "organization_id": "j2mfxwj97wnj",
            "incident_updates": [
                {
                    "body": "A fix has been implemented and we are monitoring the results.",
                    "created_at": "2013-05-29T16:07:53-06:00",
                    "display_at": "2013-05-29T16:07:53-06:00",
                    "status": "monitoring",
                    "twitter_updated_at": None,
                    "updated_at": "2013-05-29T16:09:09-06:00",
                    "wants_twitter_update": False,
                    "id": "drfcwbnpxnr6",
                    "incident_id": "lbkhbwn21v5q",
                },
                {
                    "body": "We are waiting for the cloud to come back online "
                            "and will update when we have further information",
                    "created_at": "2013-05-29T15:18:51-06:00",
                    "display_at": "2013-05-29T15:18:51-06:00",
                    "status": "identified",
                    "twitter_updated_at": None,
                    "updated_at": "2013-05-29T15:28:51-06:00",
                    "wants_twitter_update": False,
                    "id": "2rryghr4qgrh",
                    "incident_id": "lbkhbwn21v5q",
                },
                {
                    "body": "The cloud, located in Norther Virginia, has once again gone the way of the dodo.",
                    "created_at": "2013-05-29T15:08:51-06:00",
                    "display_at": "2013-05-29T15:08:51-06:00",
                    "status": "investigating",
                    "twitter_updated_at": None,
                    "updated_at": "2013-05-29T15:28:51-06:00",
                    "wants_twitter_update": False,
                    "id": "qbbsfhy5s9kk",
                    "incident_id": "lbkhbwn21v5q",
                },
            ],
            "name": "Virginia Is Down",
        },
    }
])
def test_webhook_github_status(discord_bot, test_client, mocker, data):
    """
    WHEN the '/webhook/github_status/<key>' endpoint is requested (POST) with valid data
    THEN check that the response is 'success'
    """
    mocker.patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET_KEY": "valid_key"})
    response = test_client.post('/webhook/github_status/valid_key', json=data)
    assert response.json == {"status": "success"}
    assert response.status_code == 200
