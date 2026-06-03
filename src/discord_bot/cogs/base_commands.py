# lib imports
import discord
from discord.commands import Option

# local imports
from src.common.common import avatar, bot_name, colors, org_name, version
from src.discord_bot.views import DonateCommandView
from src.discord_bot import cogs_common


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

        embed = discord.Embed(description=description, color=colors['orange'])
        embed.set_footer(text=bot_name, icon_url=avatar)

        await ctx.respond(embed=embed, ephemeral=True)

    @staticmethod
    async def get_command_help(
            ctx: discord.ApplicationContext,
            cmd: discord.command,
            group_name=None,
    ) -> str:
        permissions = cmd.default_member_permissions
        if not BaseCommandsCog.has_command_permissions(ctx=ctx, permissions=permissions):
            return ""

        description = BaseCommandsCog.command_help_title(cmd=cmd, group_name=group_name)
        description += f"{BaseCommandsCog.command_help_text(cmd=cmd)}\n"
        description += BaseCommandsCog.command_options_help(options=cmd.options)
        return f"{description}\n"

    @staticmethod
    def has_command_permissions(ctx: discord.ApplicationContext, permissions) -> bool:
        if not permissions:
            return True

        permissions_dict = {perm[0]: perm[1] for perm in permissions}
        return all(getattr(ctx.author.guild_permissions, perm, False) for perm in permissions_dict)

    @staticmethod
    def command_help_title(cmd: discord.command, group_name=None) -> str:
        if group_name:
            return f"### `/{group_name} {cmd.name}`\n"

        return f"### `/{cmd.name}`\n"

    @staticmethod
    def command_help_text(cmd: discord.command) -> str:
        if cmd.description:
            return cmd.description

        doc_lines = cmd.callback.__doc__.split('\n')
        return '\n'.join(line.strip() for line in doc_lines).split('\nParameters\n----------')[0].strip()

    @staticmethod
    def command_options_help(options: list) -> str:
        if not options:
            return ""

        description = "\n**Options:**\n"
        for option in options:
            description += (f"`{option.name}`: {option.description} "
                            f"({'Required' if option.required else 'Optional'})\n")

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
