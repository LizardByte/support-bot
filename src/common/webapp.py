# standard imports
import os
from threading import Thread
from typing import Tuple

# lib imports
import discord
from flask import Flask, jsonify, redirect, request, Response, send_from_directory
from requests_oauthlib import OAuth2Session
from werkzeug.middleware.proxy_fix import ProxyFix

# local imports
from src.common.common import app_dir, colors
from src.common import crypto
from src.common import globals
from src.common import time


DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "https://localhost:8080/discord/callback")

app = Flask(
    import_name='LizardByte-bot',
    static_folder=os.path.join(app_dir, 'assets'),
)

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


@app.route('/status')
def status():
    return "LizardByte-bot is live!"


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        directory=app.static_folder,
        path="favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@app.route("/discord/callback")
def discord_callback():
    # get all active states from the global state manager
    with globals.DISCORD_BOT.db as db:
        active_states = db['oauth_states']

    discord_oauth = OAuth2Session(DISCORD_CLIENT_ID, redirect_uri=DISCORD_REDIRECT_URI)
    token = discord_oauth.fetch_token("https://discord.com/api/oauth2/token",
                                      client_secret=DISCORD_CLIENT_SECRET,
                                      authorization_response=request.url)

    # Fetch the user's Discord profile
    response = discord_oauth.get("https://discord.com/api/users/@me")
    discord_user = response.json()

    # if the user is not in the active states, return an error
    if discord_user['id'] not in active_states:
        return "Invalid state"

    # remove the user from the active states
    del active_states[discord_user['id']]

    # Fetch the user's connected accounts
    connections_response = discord_oauth.get("https://discord.com/api/users/@me/connections")
    connections = connections_response.json()

    with globals.DISCORD_BOT.db as db:
        db['discord_users'] = db.get('discord_users', {})
        db['discord_users'][discord_user['id']] = {
            'discord_username': discord_user['username'],
            'discord_global_name': discord_user['global_name'],
            'github_id': None,
            'github_username': None,
            'token': token,  # TODO: should we store the token at all?
        }

        for connection in connections:
            if connection['type'] == 'github':
                db['discord_users'][discord_user['id']]['github_id'] = connection['id']
                db['discord_users'][discord_user['id']]['github_username'] = connection['name']

    # Redirect to our main website
    return redirect("https://app.lizardbyte.dev")


@app.route("/webhook/<source>/<key>", methods=["POST"])
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

    print(f"received webhook from {source}")
    data = request.json
    print(f"received webhook data: \n{data}")

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
