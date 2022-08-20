# standard imports
from io import BytesIO
import os

# lib imports
import requests

# local imports
from discord_helpers import get_bot_avatar

# avatar
avatar = get_bot_avatar(gravatar=os.environ['GRAVATAR_EMAIL'])

avatar_response = requests.get(url=avatar)
avatar_img = BytesIO(avatar_response.content).read()
