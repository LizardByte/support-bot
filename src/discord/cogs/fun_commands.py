# standard imports
import random

# lib imports
import discord
from discord.commands import Option
import requests

# local imports
from src.common.common import avatar, bot_name
from src.discord.views import RefundCommandView
from src.discord import cogs_common


class FunCommandsCog(discord.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(
        name="random",
        description="Get a random video game quote"
    )
    async def random_command(
            self,
            ctx: discord.ApplicationContext,
            user: Option(
                discord.Member,
                description=cogs_common.user_mention_desc,
                required=False,
            ),
    ):
        """
        Get a random video game quote.

        Parameters
        ----------
        ctx : discord.ApplicationContext
            Request message context.
        user : discord.Member
            Username to mention in response.
        """
        quotes = requests.get(url='https://app.lizardbyte.dev/uno/random-quotes/games.json').json()

        quote_index = random.choice(seq=quotes)
        quote = quote_index['quote']

        game = quote_index['game']
        character = quote_index['character']

        if game and character:
            description = f'~{character} / {game}'
        elif game:
            description = f'{game}'
        elif character:
            description = f'~{character}'
        else:
            description = None

        embed = discord.Embed(title=quote, description=description, color=0x00ff00)
        embed.set_footer(text=bot_name, icon_url=avatar)

        if user:
            await ctx.respond(user.mention, embed=embed)
        else:
            await ctx.respond(embed=embed)

    @discord.slash_command(
        name="refund",
        description="Get refund form"
    )
    async def refund_command(
            self,
            ctx: discord.ApplicationContext,
            user: Option(
                discord.Member,
                description=cogs_common.user_mention_desc,
                required=False,
            ),
    ):
        """
        Sends a discord embed, with a `Modal`.
        This command is pure satire.

        Parameters
        ----------
        ctx : discord.ApplicationContext
            Request message context.
        user : discord.Member
            Username to mention in response.
        """
        embed = discord.Embed(title="Refund request",
                              description="Original purchase price: $0.00\n\n"
                                          "Select the button below to request a full refund!",
                              color=0xDC143C)
        embed.set_footer(text=bot_name, icon_url=avatar)

        if user:
            await ctx.respond(user.mention, embed=embed, view=RefundCommandView())
        else:
            await ctx.respond(embed=embed, view=RefundCommandView())


def setup(bot: discord.Bot):
    bot.add_cog(FunCommandsCog(bot=bot))
