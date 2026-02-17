# standard imports
import asyncio
import html
import logging
import os
from threading import Thread
from typing import Tuple

# lib imports
import discord
from flask import Flask, jsonify, redirect, request, Response, send_from_directory
from flask_wtf import CSRFProtect
from requests_oauthlib import OAuth2Session
from werkzeug.middleware.proxy_fix import ProxyFix

# local imports
from src.common.common import app_dir, colors, version
from src.common import crypto
from src.common import globals
from src.common import time

# Get logger for this module
logger = logging.getLogger(__name__)


DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "https://localhost:8080/discord/callback")

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "https://localhost:8080/github/callback")

app = Flask(
    import_name='LizardByte-bot',
    static_folder=os.path.join(app_dir, 'assets'),
)
app.secret_key = os.urandom(32).hex()
csrf = CSRFProtect(app)  # Enable CSRF Protection

# this allows us to log the real IP address of the client, instead of the IP address of the proxy host
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)


status_colors_map = {
    'investigating': colors['red'],
    'identified': colors['orange'],
    'monitoring': colors['yellow'],
    'resolved': colors['green'],
    'operational': colors['green'],
    'major_outage': colors['red'],
    'partial_outage': colors['orange'],
    'degraded_performance': colors['yellow'],
}


def html_to_md(html: str) -> str:
    """
    Convert HTML to markdown.

    Parameters
    ----------
    html : str
        The HTML string to convert to markdown.

    Returns
    -------
    str
        The markdown string.
    """
    replacements = {
        '<br>': '\n',
        '<br/>': '\n',
        '<br />': '\n',
        '<strong>': '**',
        '</strong>': '**',
    }

    for old, new in replacements.items():
        html = html.replace(old, new)

    return html


@app.route('/status', methods=["GET"])
def status():
    degraded_checks = [
        getattr(globals.DISCORD_BOT, 'DEGRADED', True),
        getattr(globals.REDDIT_BOT, 'DEGRADED', True),
    ]

    s = 'ok'
    if any(degraded_checks):
        s = 'degraded'

    result = {
        "status": s,
        "version": version,
    }
    return jsonify(result)


@app.route("/favicon.ico", methods=["GET"])
def favicon():
    return send_from_directory(
        directory=app.static_folder,
        path="favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@app.route("/discord/callback", methods=["GET"])
def discord_callback():
    # errors will be in the query parameters
    if 'error' in request.args:
        return Response(html.escape(request.args['error_description']), status=400)

    # get all active states from the global state manager
    active_states = globals.DISCORD_BOT.oauth_states

    discord_oauth = OAuth2Session(DISCORD_CLIENT_ID, redirect_uri=DISCORD_REDIRECT_URI)
    token = discord_oauth.fetch_token(
        token_url="https://discord.com/api/oauth2/token",
        client_secret=DISCORD_CLIENT_SECRET,
        authorization_response=request.url
    )

    # Fetch the user's Discord profile
    response = discord_oauth.get(
        url="https://discord.com/api/users/@me",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token['access_token']}",
        },
    )
    discord_user = response.json()

    # if the user is not in the active states, return an error
    if discord_user['id'] not in active_states:
        globals.DISCORD_BOT.update_cached_message(
            author_id=discord_user['id'],
            reason='failure',
        )
        return Response("Invalid state", status=400)

    # remove the user from the active states
    del active_states[discord_user['id']]

    # Fetch the user's connected accounts
    connections_response = discord_oauth.get("https://discord.com/api/users/@me/connections")
    connections = connections_response.json()

    # Default user data
    user_data = {
        'user_id': int(discord_user['id']),
        'discord_username': discord_user['username'],
        'discord_global_name': discord_user['global_name'],
        'github_id': None,
        'github_username': None,
    }

    # Check for GitHub connections
    for connection in connections:
        if connection['type'] == 'github':
            user_data['github_id'] = int(connection['id'])
            user_data['github_username'] = connection['name']

    q = globals.DISCORD_BOT.db.query()

    with globals.DISCORD_BOT.db as db:
        # Get the discord_users table
        discord_users_table = db.table('discord_users')

        # Upsert the user data
        discord_users_table.upsert(
            user_data,
            q.user_id == int(discord_user['id'])
        )

    globals.DISCORD_BOT.update_cached_message(
        author_id=discord_user['id'],
        reason='success',
    )

    # Redirect to our main website
    return redirect("https://app.lizardbyte.dev")


@app.route("/github/callback", methods=["GET"])
def github_callback():
    # errors will be in the query parameters
    if 'error' in request.args:
        return Response(html.escape(request.args['error_description']), status=400)

    # the state is sent as a query parameter in the redirect URL
    state = request.args.get('state')

    # get all active states from the global state manager
    active_states = globals.DISCORD_BOT.oauth_states

    github_oauth = OAuth2Session(GITHUB_CLIENT_ID, redirect_uri=GITHUB_REDIRECT_URI)
    token = github_oauth.fetch_token(
        token_url="https://github.com/login/oauth/access_token",
        client_secret=GITHUB_CLIENT_SECRET,
        authorization_response=request.url
    )

    # Fetch the user's GitHub profile
    response = github_oauth.get(
        url="https://api.github.com/user",
        headers={
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {token['access_token']}",
        },
    )
    github_user = response.json()

    # if the user is not in the active states, return an error
    for discord_user_id, _state in active_states.items():
        if state == _state:
            break
    else:
        return Response("Invalid state", status=400)

    # remove the user from the active states
    del active_states[discord_user_id]

    # get discord user data
    discord_user_future = asyncio.run_coroutine_threadsafe(
        globals.DISCORD_BOT.fetch_user(int(discord_user_id)),
        globals.DISCORD_BOT.loop
    )
    discord_user = discord_user_future.result()

    q = globals.DISCORD_BOT.db.query()

    with globals.DISCORD_BOT.db as db:
        # Get the discord_users table
        discord_users_table = db.table('discord_users')

        # Create user data object
        user_data = {
            'user_id': int(discord_user_id),
            'discord_username': discord_user.name,
            'discord_global_name': discord_user.global_name,
            'github_id': int(github_user['id']),
            'github_username': github_user['login'],
        }

        # Upsert the user data (insert or update)
        discord_users_table.upsert(
            user_data,
            q.user_id == int(discord_user_id)
        )

    globals.DISCORD_BOT.update_cached_message(
        author_id=discord_user_id,
        reason='success',
    )

    # Redirect to our main website
    return redirect("https://app.lizardbyte.dev")


@app.route("/webhook/<source>/<key>", methods=["POST"])
@csrf.exempt
def webhook(source: str, key: str) -> Tuple[Response, int]:
    """
    Process webhooks from various sources.

    * GitHub sponsors: https://github.com/sponsors/LizardByte/dashboard/webhooks
    * GitHub status: https://www.githubstatus.com

    Parameters
    ----------
    source : str
        The source of the webhook (e.g., 'github_sponsors', 'github_status').
    key : str
        The secret key for the webhook. This must match an environment variable.

    Returns
    -------
    flask.Response
        Response to the webhook request
    """
    valid_sources = [
        "github_sponsors",
        "github_status",
    ]

    if source not in valid_sources:
        return jsonify({"status": "error", "message": "Invalid source"}), 400

    if key != os.getenv("GITHUB_WEBHOOK_SECRET_KEY"):
        return jsonify({"status": "error", "message": "Invalid key"}), 400

    logger.info(f"received webhook from {source}")
    data = request.json
    logger.info(f"received webhook data: \n{data}")

    # process the webhook data
    if source == "github_sponsors":
        if data['action'] == "created":
            embed = discord.Embed(
                author=discord.EmbedAuthor(
                    name=data["sponsorship"]["sponsor"]["login"],
                    url=data["sponsorship"]["sponsor"]["url"],
                    icon_url=data["sponsorship"]["sponsor"]["avatar_url"],
                ),
                color=colors['green'],
                timestamp=time.iso_to_datetime(data['sponsorship']['created_at']),
                title="New GitHub Sponsor",
            )
            globals.DISCORD_BOT.send_message(
                channel_id=os.getenv("DISCORD_SPONSORS_CHANNEL_ID"),
                embed=embed,
            )

    elif source == "github_status":
        # https://support.atlassian.com/statuspage/docs/enable-webhook-notifications

        embed = discord.Embed(
            title="GitHub Status Update",
            description=data['page']['status_description'],
            color=colors['green'],
        )

        # handle component updates
        if 'component_update' in data:
            component_update = data['component_update']
            component = data['component']
            embed = discord.Embed(
                color=status_colors_map.get(component_update['new_status'], colors['orange']),
                description=f"Status changed from {component_update['old_status']} to {component_update['new_status']}",
                timestamp=time.iso_to_datetime(component_update['created_at']),
                title=f"Component Update: {component['name']}",
            )
            embed.add_field(name="Component ID", value=component['id'])
            embed.add_field(name="Component Status", value=component['status'])

        # handle incident updates
        if 'incident' in data:
            incident = data['incident']
            try:
                update = incident['incident_updates'][0]
            except (IndexError, KeyError):
                return jsonify({"status": "error", "message": "No incident updates"}), 400

            embed = discord.Embed(
                color=status_colors_map.get(update['status'], colors['orange']),
                timestamp=time.iso_to_datetime(incident['created_at']),
                title=f"Incident: {incident['name']}",
                url=incident.get('shortlink', 'https://www.githubstatus.com'),
            )
            embed.add_field(name="Level", value=incident['impact'], inline=False)
            embed.add_field(name=update['status'], value=html_to_md(update['body']), inline=False)

        globals.DISCORD_BOT.send_message(
            channel_id=os.getenv("DISCORD_GITHUB_STATUS_CHANNEL_ID"),
            embed=embed,
        )

    return jsonify({"status": "success"}), 200


def run():
    cert_file, key_file = crypto.initialize_certificate()

    app.run(
        host="0.0.0.0",
        port=8080,
        ssl_context=(cert_file, key_file)
    )


def start():
    server = Thread(
        name="Flask",
        daemon=True,
        target=run,
    )
    server.start()
