# standard imports
import asyncio
import os
import threading

# lib imports
import discord

# local imports
from src.common import bot_name, get_avatar_bytes, org_name
from src.discord.tasks import daily_task
from src.discord.views import DonateCommandView


class Bot(discord.Bot):
    """
    Discord bot class.

    This class extends the discord.Bot class to include additional functionality. The class will automatically
    enable all intents and sync commands on startup. The class will also update the bot presence, username, and avatar
    when the bot is ready.
    """
    def __init__(self, *args, **kwargs):
        if 'intents' not in kwargs:
            intents = discord.Intents.all()
            kwargs['intents'] = intents
        if 'auto_sync_commands' not in kwargs:
            kwargs['auto_sync_commands'] = True
        super().__init__(*args, **kwargs)

        self.bot_thread = threading.Thread(target=lambda: None)
        self.token = os.environ['DISCORD_BOT_TOKEN']

        self.load_extension(
            name='src.discord.cogs',
            recursive=True,
            store=False,
        )

    async def on_ready(self):
        """
        Bot on ready event.

        This function runs when the discord bot is ready. The function will update the bot presence, update the username
        and avatar, and start daily tasks.
        """
        print(f'py-cord version: {discord.__version__}')
        print(f'Logged in as {self.user.name} (ID: {self.user.id})')
        print(f'Servers connected to: {self.guilds}')

        # update the username and avatar
        avatar_img = get_avatar_bytes()
        if await self.user.avatar.read() != avatar_img or self.user.name != bot_name:
            await self.user.edit(username=bot_name, avatar=avatar_img)

        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name=f"the {org_name} server")
        )

        self.add_view(DonateCommandView())  # register view for persistent listening

        await self.sync_commands()

        try:
            os.environ['DAILY_TASKS']
        except KeyError:
            daily_task.start(bot=self)
        else:
            if os.environ['DAILY_TASKS'].lower() == 'true':
                daily_task.start(bot=self)
            else:
                print("'DAILY_TASKS' environment variable is disabled")

    def start_threaded(self):
        try:
            # Login the bot in a separate thread
            self.bot_thread = threading.Thread(
                target=self.loop.run_until_complete,
                args=(self.start(token=self.token),),
                daemon=True
            )
            self.bot_thread.start()
        except KeyboardInterrupt:
            print("Keyboard Interrupt Detected")
            self.stop()

    def stop(self, future: asyncio.Future = None):
        print("Attempting to stop daily tasks")
        daily_task.stop()
        print("Attempting to close bot connection")
        if self.bot_thread is not None and self.bot_thread.is_alive():
            asyncio.run_coroutine_threadsafe(self.close(), self.loop)
            self.bot_thread.join()
        print("Closed bot")

        # Set a result for the future to mark it as done (unit testing)
        if future and not future.done():
            future.set_result(None)
