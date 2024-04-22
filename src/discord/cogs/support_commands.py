# lib imports
import discord
from discord.commands import Option

# local imports
from src.common import avatar, bot_name
from src.discord.views import DocsCommandView
from src.discord import cogs_common


class SupportCommandsCog(discord.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(
        name="docs",
        description="Get docs for any project."
    )
    async def docs_command(
            self,
            ctx: discord.ApplicationContext,
            user: Option(
                discord.Member,
                description=cogs_common.user_mention_desc,
                required=False,
            ),
    ):
        """
        Sends a discord embed, with `Select Menus` allowing the user to select the specific documentation,
        to the server and channel where the command was issued.

        Parameters
        ----------
        ctx : discord.ApplicationContext
            Request message context.
        user : discord.Member
            Username to mention in response.
        """
        embed = discord.Embed(title="Select a project", color=0xF1C232)
        embed.set_footer(text=bot_name, icon_url=avatar)

        if user:
            await ctx.respond(
                f'{ctx.author.mention}, {user.mention}',
                embed=embed,
                ephemeral=False,
                view=DocsCommandView(ctx=ctx)
            )
        else:
            await ctx.respond(
                f'{ctx.author.mention}',
                embed=embed,
                ephemeral=False,
                view=DocsCommandView(ctx=ctx)
            )


def setup(bot: discord.Bot):
    bot.add_cog(SupportCommandsCog(bot=bot))
