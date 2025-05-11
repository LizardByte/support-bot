# this file tests the reddit bot using Betamax to record and replay HTTP interactions
# See: https://leviroth.github.io/2017-05-16-testing-reddit-bots-with-betamax/

# standard imports
from base64 import b64encode
import inspect
import json
import os
import shelve
from unittest.mock import patch
from urllib.parse import quote_plus

# lib imports
from betamax import Betamax, cassette
from betamax_serializers.pretty_json import PrettyJSONSerializer
from praw.config import _NotSet
import pytest

# local imports
from src.reddit_bot.bot import Bot

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

    @pytest.fixture(scope='session')
    def slash_command_comment(self, bot, recorder):
        comment = bot.reddit.comment(id='l20s21b')
        with recorder.use_cassette(f'fixture_{inspect.currentframe().f_code.co_name}'):
            assert comment.body == '/sunshine vban'

        return comment

    @pytest.fixture(scope='session')
    def _submission(self, bot, recorder):
        s = bot.reddit.submission(id='w03cku')
        with recorder.use_cassette(f'fixture_{inspect.currentframe().f_code.co_name}'):
            assert s.author

        return s

    def test_validate_env(self, bot):
        with patch.dict(
                os.environ, {
                    "DISCORD_REDDIT_CHANNEL_ID": "test",
                    "PRAW_CLIENT_ID": "test",
                    "PRAW_CLIENT_SECRET": "test",
                    "REDDIT_PASSWORD": "test",
                    "REDDIT_USERNAME": "test",
                }):
            assert bot.validate_env()

    def test_migrate_shelve(self, bot):
        with patch.object(shelve, 'open') as mock_open:
            bot.migrate_shelve()
            mock_open.assert_called_once_with(bot.db)
        with shelve.open(bot.db) as db:
            assert db.get('comments') is not None
            assert db.get('submissions') is not None

    def test_migrate_last_online(self, bot):
        f = os.path.join(bot.data_dir, 'last_online')
        if not os.path.isfile(f):
            with open(f, 'w') as file:
                file.write('1234')
        assert os.path.isfile(f)

        bot.migrate_last_online()
        assert not os.path.isfile(f)

    def test_process_comment(self, bot, recorder, request, slash_command_comment):
        with recorder.use_cassette(request.node.name):
            bot.process_comment(comment=slash_command_comment)
        with bot.lock, shelve.open(bot.db) as db:
            assert slash_command_comment.id in db['comments']
            assert db['comments'][slash_command_comment.id]['author'] == str(slash_command_comment.author)
            assert db['comments'][slash_command_comment.id]['body'] == slash_command_comment.body
            assert db['comments'][slash_command_comment.id]['processed']
            assert db['comments'][slash_command_comment.id]['slash_command']['project'] == 'sunshine'
            assert db['comments'][slash_command_comment.id]['slash_command']['command'] == 'vban'

    def test_process_submission(self, bot, discord_bot, recorder, request, _submission):
        with recorder.use_cassette(request.node.name):
            bot.process_submission(submission=_submission)
        with bot.lock, shelve.open(bot.db) as db:
            assert _submission.id in db['submissions']
            assert db['submissions'][_submission.id]['author'] == str(_submission.author)
            assert db['submissions'][_submission.id]['title'] == _submission.title
            assert db['submissions'][_submission.id]['bot_discord']['sent'] is True
            assert db['submissions'][_submission.id]['bot_discord']['sent_utc']

    def test_comment_loop(self, bot, recorder, request):
        with recorder.use_cassette(request.node.name):
            comment = bot._comment_loop(test=True)
            assert comment.author

    def test_submission_loop(self, bot, discord_bot, recorder, request):
        with recorder.use_cassette(request.node.name):
            submission = bot._submission_loop(test=True)
            assert submission.author
