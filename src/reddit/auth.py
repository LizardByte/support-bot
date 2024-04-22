# standard imports
import os
import random
import socket

# lib imports
import praw

"""
This module is deprecated and no longer used by the project, this is left here for reference only and may be removed
in the future. Since no individual users need to authorize our app, we can just use password flow.

To use this the following changes need to be made to the src.reddit.bot.py:

1. Imports
- from praw.util.token_manager import FileTokenManager
- from src.reddit import auth

2. Bot class, __init__ method:
- self.refresh_token_file = os.path.join(self.data_dir, 'refresh_token')
- self.initialize_refresh_token_file()
- self.refresh_token_manager = FileTokenManager(self.refresh_token_file)

3. Bot class, __init__ method, self.reddit object:
- token_manager=self.refresh_token_manager,

4. Call the auth.initialize_refresh_token_file method with the appropriate parameters
"""


def initialize_refresh_token_file(refresh_token_file: str, redirect_uri: str, user_agent: str) -> bool:
    if os.path.isfile(refresh_token_file):
        return True

    # https://www.reddit.com/api/v1/scopes.json
    scopes = [
        'read',  # Access posts and comments through my account.
    ]

    reddit_auth = praw.Reddit(
        client_id=os.environ['PRAW_CLIENT_ID'],
        client_secret=os.environ['PRAW_CLIENT_SECRET'],
        redirect_uri=redirect_uri,
        user_agent=user_agent,
    )

    state = str(random.randint(0, 65000))
    url = reddit_auth.auth.url(scopes=scopes, state=state, duration="permanent")
    print(f"Now open this url in your browser: {url}")

    client, data = receive_connection()
    param_tokens = data.split(" ", 2)[1].split("?", 1)[1].split("&")
    params = {
        key: value for (key, value) in [token.split("=") for token in param_tokens]
    }

    if state != params["state"]:
        send_message(
            client,
            f"State mismatch. Expected: {state} Received: {params['state']}",
        )
        return False
    elif "error" in params:
        send_message(client, params["error"])
        return False

    refresh_token = reddit_auth.auth.authorize(params["code"])
    with open(refresh_token_file, 'w+') as f:
        f.write(refresh_token)

    send_message(client, f"Refresh token: {refresh_token}")
    print('Refresh token has been written to "refresh_token" file')
    return True


def receive_connection() -> tuple[socket.socket, str]:
    """
    Wait for and then return a connected socket.

    Opens a TCP connection on port 8080, and waits for a single client.

    Returns
    -------
    tuple[socket.socket, str]
        The connected socket and the data received.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', 8080))
    server.listen()
    # Handle one request from the client
    while True:
        (clientSocket, clientAddress) = server.accept()
        data = clientSocket.recv(1024)

        if data != b'':
            # Wait until we receive the data from reddit
            if data.startswith(b'GET /?state='):
                # Send back what you received
                clientSocket.send(data)

                break
    server.close()
    return clientSocket, data.decode("utf-8")


def send_message(client: socket.socket, message: str):
    """
    Send a message to the client and close the connection.

    Parameters
    ----------
    client : socket.socket
        The client socket.
    message : str
        The message to send.
    """
    print(f'message: {message}')
    client.send(f"HTTP/1.1 200 OK\r\n\r\n{message}".encode("utf-8"))
    client.close()
