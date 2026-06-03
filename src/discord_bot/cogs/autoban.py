# standard imports
import logging
import os

# lib imports
import discord
from discord.ext import commands

# Get logger for this module
logger = logging.getLogger(__name__)


class AutoBanCog(discord.Cog):
    """
    Discord cog that automatically bans any user who posts in the configured autoban channel.
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Listen for messages and ban the author if the message is in the autoban channel.

        Any message sent to the channel defined by ``DISCORD_AUTOBAN_CHANNEL_ID`` will result in
        the author being banned from the guild. All messages from the user within the past 7 days
        are also deleted. Bot messages are ignored.

        Parameters
        ----------
        message : discord.Message
            The message object that triggered this event.
        """
        if message.author.bot:
            return

        autoban_channel_id = os.getenv('DISCORD_AUTOBAN_CHANNEL_ID')
        if not autoban_channel_id:
            return

        if message.channel.id != int(autoban_channel_id):
            return

        guild = message.guild
        if not guild:
            return

        try:
            await guild.ban(
                user=message.author,
                reason="Automatic ban: posted in restricted channel.",
                delete_message_seconds=604800,  # Delete messages from the past 7 days
            )
            # repr() sanitizes the content, escaping newlines and other special characters
            # to prevent log injection attacks.
            safe_content = repr(message.content)
            attachment_urls = [a.url for a in message.attachments]
            logger.warning(
                "Auto-banned user %s (%s) for posting in channel %s (%s). "
                "Message content: %s. "
                "Attachments: %s.",
                message.author,
                message.author.id,
                message.channel.name,
                message.channel.id,
                safe_content,
                attachment_urls,
            )
        except discord.Forbidden:
            logger.error(
                "Missing permissions to ban user %s (%s) in guild %s (%s).",
                message.author,
                message.author.id,
                guild.name,
                guild.id,
            )
        except discord.HTTPException:
            logger.exception(
                "HTTP error while banning user %s (%s)",
                message.author,
                message.author.id,
            )


def setup(bot: discord.Bot):
    bot.add_cog(AutoBanCog(bot=bot))
