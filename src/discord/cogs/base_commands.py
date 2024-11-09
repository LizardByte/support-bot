# lib imports
import discord
from discord.commands import Option

# local imports
from src.common.common import avatar, bot_name, org_name, version
from src.discord.views import DonateCommandView
from src.discord import cogs_common


class BaseCommandsCog(discord.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(
        name="help",
        description=f"Get help with {bot_name}"
    )
    async def help_command(
            self,
            ctx: discord.ApplicationContext,
    ):
        """
        Get help with the bot.

        Parameters
        ----------
        ctx : discord.ApplicationContext
            Request message context.
        """
        description = ""

        for cmd in self.bot.commands:
            if isinstance(cmd, discord.SlashCommandGroup):
                for sub_cmd in cmd.subcommands:
                    description += await self.get_command_help(ctx=ctx, cmd=sub_cmd, group_name=cmd.name)
            else:
                description += await self.get_command_help(ctx=ctx, cmd=cmd)

        description += f"\n\nVersion: {version}\n"

        embed = discord.Embed(description=description, color=0xE5A00D)
        embed.set_footer(text=bot_name, icon_url=avatar)

        await ctx.respond(embed=embed, ephemeral=True)

    @staticmethod
    async def get_command_help(
            ctx: discord.ApplicationContext,
            cmd: discord.command,
            group_name=None,
    ) -> str:
        description = ""
        permissions = cmd.default_member_permissions
        has_permissions = True
        if permissions:
            permissions_dict = {perm[0]: perm[1] for perm in permissions}
            has_permissions = all(getattr(ctx.author.guild_permissions, perm, False) for perm in permissions_dict)
        if has_permissions:
            doc_help = cmd.description
            if not doc_help:
                doc_lines = cmd.callback.__doc__.split('\n')
                doc_help = '\n'.join(line.strip() for line in doc_lines).split('\nParameters\n----------')[0].strip()
            if group_name:
                description = f"### `/{group_name} {cmd.name}`\n"
            else:
                description = f"### `/{cmd.name}`\n"
            description += f"{doc_help}\n"
            if cmd.options:
                description += "\n**Options:**\n"
                for option in cmd.options:
                    description += (f"`{option.name}`: {option.description} "
                                    f"({'Required' if option.required else 'Optional'})\n")
            description += "\n"
        return description

    @discord.slash_command(
        name="donate",
        description=f"Support the development of {org_name}"
    )
    async def donate_command(
            self,
            ctx: discord.ApplicationContext,
            user: Option(
                discord.Member,
                description=cogs_common.user_mention_desc,
                required=False,
            ),
    ):
        """
        Sends a discord view, with various donation urls, to the server and channel where the
        command was issued.

        Parameters
        ----------
        ctx : discord.ApplicationContext
            Request message context.
        user : discord.Member
            Username to mention in response.
        """
        if user:
            await ctx.respond(f'Thank you for your support {user.mention}!', view=DonateCommandView())
        else:
            await ctx.respond('Thank you for your support!', view=DonateCommandView())


def setup(bot: discord.Bot):
    bot.add_cog(BaseCommandsCog(bot=bot))
