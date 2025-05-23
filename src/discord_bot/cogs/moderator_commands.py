# standard imports
import time
from typing import Union

# lib imports
import discord
from discord.commands import Option

# local imports
from src.common.common import avatar, bot_name, colors

# constants
recommended_channel_desc = 'Select the recommended channel'  # hack for flake8 F722
user_info_option_desc = 'User to get information about'  # hack for flake8 F722


class ModeratorCommandsCog(discord.Cog):
    def __init__(self, bot):
        self.bot = bot

    mod_commands = discord.SlashCommandGroup(
        name="mod",
        description="Moderator commands",
        default_member_permissions=discord.Permissions(manage_guild=True),
    )

    @mod_commands.command(
        name="channel",
        description="Suggest to move discussion to a different channel"
    )
    async def channel_command(
            self,
            ctx: discord.ApplicationContext,
            recommended_channel: Option(
                Union[discord.ForumChannel, discord.TextChannel],
                description=recommended_channel_desc,
                required=True,
            ),
    ):
        """
        Sends a discord embed, with a suggestion to move discussion to a different channel.
        Additionally, the command will let the users know how to gain access to additional channels.

        Parameters
        ----------
        ctx : discord.ApplicationContext
            Request message context.
        recommended_channel : Union[discord.ForumChannel, discord.TextChannel]
            The recommended channel to move discussion to.
        """
        categories_map = {
            "dev lounge": "roles",
            "insider lounge": "roles",
        }

        embed = discord.Embed(
            title="Incorrect channel",
            description=f"Please move discussion to {recommended_channel.mention}",
            color=colors['orange'],
        )

        permission_ch_id = ''
        try:
            category_name = recommended_channel.category.name.lower()
        except AttributeError:
            pass
        else:
            if category_name in categories_map:
                for _ in ctx.guild.text_channels:
                    if _.name == categories_map[category_name]:
                        permission_ch_id = f'<#{_.id}>\n'
                        break

        # special channel mentions
        # https://github.com/Pycord-Development/pycord/discussions/2020#discussioncomment-5666672
        embed.add_field(
            name=f"Need access to `{recommended_channel}`?",
            value=f"You may need to give yourself access in one of these channels:\n {permission_ch_id}"
                  "<id:customize>\n <id:browse>."
        )

        embed.set_footer(text=bot_name, icon_url=avatar)

        await ctx.respond(embed=embed)

    @mod_commands.command(
        name="sync",
        description="Sync slash commands",
    )
    async def sync_command(
            self,
            ctx: discord.ApplicationContext,
    ):
        """
        Sync slash commands with the discord server from which the command was issued.

        Parameters
        ----------
        ctx : discord.ApplicationContext
            Request message context.
        """
        await ctx.defer(ephemeral=True)

        now = time.time()
        await self.bot.sync_commands(
            force=True,
            guild_ids=[ctx.guild_id],
        )
        duration = int(time.time() - now)
        await ctx.respond("""Synced commands!

Sync duration: {}s
Commands not showing up? Try restarting discord or clearing cache.
""".format(duration), ephemeral=True)

    @mod_commands.command(
        name="user-info",
        description="Get user information about a Discord user",
    )
    async def user_info_command(
            self,
            ctx: discord.ApplicationContext,
            user: Option(
                discord.User,
                description=user_info_option_desc,
                required=False,
            ),
    ):
        """
        Get user information about a Discord user.

        Parameters
        ----------
        ctx : discord.ApplicationContext
            Request message context.
        user : discord.User
            User to get information about.
        """
        target_user = user or ctx.author
        embed = discord.Embed(
            fields=[
                discord.EmbedField(name="ID", value=str(target_user.id), inline=False),  # User ID
                discord.EmbedField(
                    name="Joined Discord at",
                    value=f'{discord.utils.format_dt(target_user.created_at, "R")}\n'
                          f'{discord.utils.format_dt(target_user.created_at, "F")}',
                    inline=False,
                ),  # When the user's account was created
            ],
        )
        embed.set_author(name=target_user.name)
        embed.set_thumbnail(url=target_user.display_avatar.url)

        embed.colour = target_user.color if target_user.color.value else colors['white']

        with self.bot.db as db:
            users_table = db.table('discord_users')
            user_doc = users_table.get(self.bot.db.query().id == str(target_user.id))
            if user_doc and user_doc.get('github_username'):
                embed.add_field(
                    name="GitHub",
                    value=f"[{user_doc['github_username']}](https://github.com/{user_doc['github_username']})",
                    inline=False,
                )

        if isinstance(target_user, discord.User):  # Checks if the user in the server
            embed.set_footer(text="This user is not in this server.")
            await ctx.respond(embeds=[embed])
            return

        # We end up here if the user is a discord.Member object
        embed.add_field(
            name="Joined Server at",
            value=f'{discord.utils.format_dt(target_user.joined_at, "R")}\n'
                  f'{discord.utils.format_dt(target_user.joined_at, "F")}',
            inline=False,
        )  # When the user joined the server

        # get User Roles
        roles = [role.name for role in target_user.roles]
        roles.pop(0)  # remove @everyone role
        embed.add_field(
            name="Server Roles",
            value='\n'.join(roles) if roles else "No roles",
            inline=False,
        )

        # get User Status, such as Server Owner, Server Moderator, Server Admin, etc.
        user_status = []
        if target_user.guild.owner_id == target_user.id:
            user_status.append("Server Owner")
        if target_user.guild_permissions.administrator:
            user_status.append("Server Admin")
        if target_user.guild_permissions.manage_guild:
            user_status.append("Server Moderator")
        embed.add_field(
            name="User Status",
            value='\n'.join(user_status),
            inline=False,
        )

        if target_user.premium_since:  # If the user is boosting the server
            boosting_value = (f'{discord.utils.format_dt(target_user.premium_since, "R")}\n'
                              f'{discord.utils.format_dt(target_user.premium_since, "F")}')
        else:
            boosting_value = "Not boosting"
        embed.add_field(
            name="Boosting Since",
            value=boosting_value,
            inline=False,
        )

        await ctx.respond(embeds=[embed])  # Sends the embed


def setup(bot: discord.Bot):
    bot.add_cog(ModeratorCommandsCog(bot=bot))
