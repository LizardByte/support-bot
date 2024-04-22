# this file tests the reddit bot using Betamax to record and replay HTTP interactions
# See: https://leviroth.github.io/2017-05-16-testing-reddit-bots-with-betamax/

# standard imports
from base64 import b64encode
import json
import os
import unittest
from unittest.mock import patch, MagicMock
from urllib.parse import quote_plus

# lib imports
from betamax import Betamax, cassette
from betamax_serializers.pretty_json import PrettyJSONSerializer
from praw.config import _NotSet
import pytest
from praw.models import Submission, Comment

# local imports
from src.reddit.bot import Bot

Betamax.register_serializer(PrettyJSONSerializer)


def b64_string(input_string: str) -> str:
    """Return a base64 encoded string (not bytes) from input_string."""
    return b64encode(input_string.encode('utf-8')).decode('utf-8')


def sanitize_tokens(
        interaction: cassette.cassette.Interaction,
        current_cassette: cassette.cassette.Cassette,
):
    """Add Betamax placeholder to filter access token."""
    request = interaction.data['request']
    response = interaction.data['response']

    # First, check if the request is for an access token.
    if 'api/v1/access_token' in request['uri'] and response['status']['code'] == 200:
        body = response['body']['string']

        token_types = [
            'access_token',
            'refresh_token',
        ]
        for token_type in token_types:
            try:
                token = json.loads(body)[token_type]
            except (KeyError, TypeError, ValueError):
                continue

            # If we succeeded in finding the token, add it to the placeholders for this cassette.
            current_cassette.placeholders.append(
                cassette.cassette.Placeholder(placeholder='<{}>'.format(token_type.upper()), replace=token)
            )

    # Check if the request has an Authorization header.
    if 'Authorization' in request['headers']:
        # If the request has an Authorization header, sanitize the bearer token.
        token = request['headers']['Authorization'][0].split(' ')[1]  # Get the token part from "bearer <token>"
        current_cassette.placeholders.append(
            cassette.cassette.Placeholder(placeholder='<BEARER_TOKEN>', replace=token)
        )


def patch_content_length(
    interaction: cassette.cassette.Interaction,
    current_cassette: cassette.cassette.Cassette,
):
    """Fix the Content-Length header in the response after sanitizing tokens."""
    request_uri = interaction.data['request']['uri']
    response = interaction.data['response']

    # # We only care about requests that generate an access token.
    if ('api/v1/access_token' not in request_uri or
            response['status']['code'] != 200):
        return
    body = response['body']['string']
    content_length = len(body.encode('utf-8'))
    response['headers']['Content-Length'] = [str(content_length)]


def get_placeholders(bot: Bot) -> dict[str, str]:
    """Prepare placeholders for sensitive information."""
    filter_keys = [
        'client_id',
        'client_secret',
        'password',
        'username',
    ]

    placeholders = {
        attr: getattr(bot.reddit.config, attr)
        for attr in filter_keys}

    # Check if attributes exist and are not _NotSet before using them
    for key in placeholders:
        if isinstance(placeholders[key], _NotSet):
            placeholders[key] = ''

    # Password is sent URL-encoded.
    placeholders['password'] = quote_plus(placeholders['password'])

    # Client ID and secret are sent in base-64 encoding.
    placeholders['basic_auth'] = b64_string(
        "{}:{}".format(placeholders['client_id'],
                       placeholders['client_secret'])
    )

    return placeholders


class TestBot:
    @pytest.fixture(scope='session')
    def bot(self):
        return Bot(
            user_agent='Test suite',
        )

    @pytest.fixture(scope='session', autouse=True)
    def betamax_config(self, bot):
        record_mode = 'none' if os.environ.get('GITHUB_PYTEST') else 'once'

        with Betamax.configure() as config:
            config.cassette_library_dir = 'tests/fixtures/cassettes'
            config.default_cassette_options['record_mode'] = record_mode
            config.default_cassette_options['serialize_with'] = 'prettyjson'
            config.before_record(callback=sanitize_tokens)
            config.before_playback(callback=patch_content_length)

            # Add placeholders for sensitive information.
            for key, value in get_placeholders(bot).items():
                config.define_cassette_placeholder('<{}>'.format(key.upper()), value)

    @pytest.fixture(scope='session')
    def session(self, bot):
        http = bot.reddit._core._requestor._http
        http.headers['Accept-Encoding'] = 'identity'  # ensure response is human readable
        return http

    @pytest.fixture(scope='session')
    def recorder(self, session):
        return Betamax(session)

    def test_validate_env(self, bot):
        with patch.dict(
                os.environ, {
                    "DISCORD_WEBHOOK": "test",
                    "PRAW_CLIENT_ID": "test",
                    "PRAW_CLIENT_SECRET": "test",
                    "REDDIT_PASSWORD": "test",
                    "REDDIT_USERNAME": "test",
                }):
            assert bot.validate_env()

    def test_process_comment(self, bot):
        comment = MagicMock(spec=Comment)
        with patch.object(bot, 'process_comment') as mock_process_comment:
            bot.process_comment(comment)
            mock_process_comment.assert_called_once_with(comment)

    def test_process_submission(self, bot):
        submission = MagicMock(spec=Submission)
        with patch.object(bot, 'process_submission') as mock_process_submission:
            bot.process_submission(submission)
            mock_process_submission.assert_called_once_with(submission)

    def test_last_online_writer(self, bot):
        with patch('builtins.open', unittest.mock.mock_open()) as mock_file:
            bot.last_online_writer()
            mock_file.assert_called_once_with(bot.last_online_file, 'w')

    def test_get_last_online(self, bot):
        with patch('builtins.open', unittest.mock.mock_open(read_data='1234567890')) as mock_file:
            assert bot.get_last_online() == 1234567890
            mock_file.assert_called_once_with(bot.last_online_file, 'r')

    def test_submission(self, bot, recorder, request):
        submission = bot.reddit.submission(id='w03cku')
        with recorder.use_cassette(request.node.name):
            assert submission.author

    def test_comment_loop(self, bot, recorder, request):
        with recorder.use_cassette(request.node.name):
            comment = bot._comment_loop(test=True)
            assert comment.author

    def test_submission_loop(self, bot, recorder, request):
        with recorder.use_cassette(request.node.name):
            submission = bot._submission_loop(test=True)
            assert submission.author
