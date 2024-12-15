# standard imports
import asyncio
import os
import threading
from typing import Literal, Optional

# lib imports
import discord

# local imports
from src.common.common import bot_name, data_dir, get_avatar_bytes, org_name
from src.common.database import Database
from src.discord.views import DonateCommandView


class Bot(discord.Bot):
    """
    Discord bot class.

    This class extends the discord.Bot class to include additional functionality. The class will automatically
    enable all intents and sync commands on startup. The class will also update the bot presence, username, and avatar
    when the bot is ready.
    """
    def __init__(self, *args, **kwargs):
        # tasks need to be imported here to avoid circular imports
        from src.discord import tasks

        if 'intents' not in kwargs:
            intents = discord.Intents.all()
            kwargs['intents'] = intents
        if 'auto_sync_commands' not in kwargs:
            kwargs['auto_sync_commands'] = True
        super().__init__(*args, **kwargs)

        self.DEGRADED = False

        self.bot_thread = threading.Thread(target=lambda: None)
        self.token = os.environ['DISCORD_BOT_TOKEN']
        self.db = Database(db_path=os.path.join(data_dir, 'discord_bot_database'))
        self.ephemeral_db = {}
        self.clean_ephemeral_cache = tasks.clean_ephemeral_cache
        self.daily_task = tasks.daily_task
        self.role_update_task = tasks.role_update_task

        self.load_extension(
            name='src.discord.cogs',
            recursive=True,
            store=False,
        )

        with self.db as db:
            db['oauth_states'] = {}  # clear any oauth states from previous sessions

    async def on_ready(self):
        """
        Bot on ready event.

        This function runs when the discord bot is ready. The function will update the bot presence, update the username
        and avatar, and start tasks.
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

        self.clean_ephemeral_cache.start(bot=self)
        self.role_update_task.start(bot=self)

        try:
            os.environ['DAILY_TASKS']
        except KeyError:
            self.daily_task.start(bot=self)
        else:
            if os.environ['DAILY_TASKS'].lower() == 'true':
                self.daily_task.start(bot=self)
            else:
                print("'DAILY_TASKS' environment variable is disabled")

        await self.sync_commands()

    async def async_send_message(
            self,
            channel_id: int,
            message: str = None,
            embed: discord.Embed = None,
    ) -> Optional[discord.Message]:
        """
        Send a message to a specific channel asynchronously. If the embeds are too large, they will be shortened.
        Additionally, if the total size of the embeds is too large, they will be sent in separate messages.

        Parameters
        ----------
        channel_id : int
            The ID of the channel to send the message to.
        message : str, optional
            The message to send.
        embed : discord.Embed, optional
            The embed to send.

        Returns
        -------
        discord.Message
            The message that was sent.
        """
        # ensure we have a message or embeds to send
        if not message and not embed:
            return

        if embed and len(embed) > 6000:
            cut_length = len(embed) - 6000 + 3
            embed.description = embed.description[:-cut_length] + "..."
        if embed and embed.description and len(embed.description) > 4096:
            cut_length = len(embed.description) - 4096 + 3
            embed.description = embed.description[:-cut_length] + "..."

        channel = await self.fetch_channel(channel_id)

        try:
            return await channel.send(content=message, embed=embed)
        except Exception as e:
            print(f"Error sending message: {e}")
            self.DEGRADED = True

    def send_message(
            self,
            channel_id: int,
            message: str = None,
            embed: discord.Embed = None,
    ) -> discord.Message:
        """
        Send a message to a specific channel synchronously.

        Parameters
        ----------
        channel_id : int
            The ID of the channel to send the message to.
        message : str, optional
            The message to send.
        embed : discord.Embed, optional
            The embed to send.

        Returns
        -------
        discord.Message
            The message that was sent.
        """
        future = asyncio.run_coroutine_threadsafe(
            self.async_send_message(
                channel_id=channel_id,
                message=message,
                embed=embed,
            ), self.loop)
        return future.result()

    async def async_update_cached_message(
            self,
            author_id: int,
            reason: str,
    ) -> bool:
        """
        Update the original message with the reason asynchronously.

        After the message is updated, it will be removed from the cache.

        Parameters
        ----------
        author_id : int
            Author ID to update the cache.
        reason : str
            Reason to update the cache. Must be one of the following: 'duplicate', 'failure', 'success', 'timeout'.

        Returns
        -------
        bool
            True if the message was updated, False otherwise.
        """
        reasons = {
            'duplicate': "This request was invalidated due to a new request.",
            'failure': "An error occurred while linking your GitHub account.",
            'success': "Your GitHub account is now linked.",
            'timeout': "The request has timed out.",
        }

        db = self.ephemeral_db
        db['github_cache_context'] = db.get('github_cache_context', {})

        if str(author_id) not in db['github_cache_context']:
            return False

        await db['github_cache_context'][str(author_id)]['response'].edit(
            content=reasons[reason],
        )

        # remove the context from the cache
        del db['github_cache_context'][str(author_id)]

        return True

    def update_cached_message(
            self,
            author_id: int,
            reason: str,
    ) -> bool:
        """
        Update the original message with the reason synchronously.

        After the message is updated, it will be removed from the cache.

        Parameters
        ----------
        author_id : int
            Author ID to update the cache.
        reason : str
            Reason to update the cache. Must be one of the following: 'duplicate', 'failure', 'success', 'timeout'.

        Returns
        -------
        bool
            True if the message was updated, False otherwise.
        """
        future = asyncio.run_coroutine_threadsafe(
            self.async_update_cached_message(
                author_id=author_id,
                reason=reason,
            ), self.loop)
        return future.result()

    def create_thread(
            self,
            message: discord.Message,
            name: str,
            auto_archive_duration: Literal[60, 1440, 4320, 10080] = discord.MISSING,
            slowmode_delay: int = discord.MISSING,
    ) -> discord.Thread:
        """
        Create a thread from a message.

        Parameters
        ----------
        message : discord.Message
            The message to create the thread from.
        name : str
            The name of the thread.
        auto_archive_duration : Literal[60, 1440, 4320, 10080], optional
            The duration in minutes before the thread is automatically archived.
        slowmode_delay : int, optional
            The slowmode delay for the thread.

        Returns
        -------
        discord.Thread
            The thread that was created.
        """
        future = asyncio.run_coroutine_threadsafe(
            message.create_thread(
                name=name,
                auto_archive_duration=auto_archive_duration,
                slowmode_delay=slowmode_delay,
            ), self.loop)
        return future.result()

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
            self.DEGRADED = True
            self.stop()

    def stop(self, future: asyncio.Future = None):
        print("Attempting to stop tasks")
        self.DEGRADED = True
        self.daily_task.stop()
        self.role_update_task.stop()
        self.clean_ephemeral_cache.stop()
        print("Attempting to close bot connection")
        if self.bot_thread is not None and self.bot_thread.is_alive():
            asyncio.run_coroutine_threadsafe(self.close(), self.loop)
            self.bot_thread.join()
        print("Closed bot")
