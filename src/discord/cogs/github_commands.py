# standard imports
import os

# lib imports
import discord
from requests_oauthlib import OAuth2Session

# local imports
from src.common import sponsors


class GitHubCommandsCog(discord.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(
        name="get_sponsors",
        description="Get list of GitHub sponsors",
        default_member_permissions=discord.Permissions(manage_guild=True),
    )
    async def get_sponsors(
            self,
            ctx: discord.ApplicationContext,
    ):
        """
        Get list of GitHub sponsors.

        Parameters
        ----------
        ctx : discord.ApplicationContext
            Request message context.
        """
        data = sponsors.get_github_sponsors()

        if not data:
            await ctx.respond("An error occurred while fetching sponsors.", ephemeral=True)
            return

        message = "List of GitHub sponsors"
        for edge in data['data']['organization']['sponsorshipsAsMaintainer']['edges']:
            sponsor = edge['node']['sponsorEntity']
            tier = edge['node'].get('tier', {})
            tier_info = f" - Tier: {tier.get('name', 'N/A')} (${tier.get('monthlyPriceInDollars', 'N/A')}/month)"
            message += f"\n* [{sponsor['login']}]({sponsor['url']}){tier_info}"

        embed = discord.Embed(title="GitHub Sponsors", color=0x00ff00, description=message)

        await ctx.respond(embed=embed, ephemeral=True)

    @discord.slash_command(
        name="link_github",
        description="Validate GitHub sponsor status"
    )
    async def link_github(self, ctx: discord.ApplicationContext):
        """
        Link Discord account with GitHub account, by validating Discord user's "GitHub" connected account status.

        User to login to Discord via OAuth2, and check if their connected GitHub account is a sponsor of the project.

        Parameters
        ----------
        ctx : discord.ApplicationContext
            Request message context.
        """
        discord_oauth = OAuth2Session(
            os.environ['DISCORD_CLIENT_ID'],
            redirect_uri=os.environ['DISCORD_REDIRECT_URI'],
            scope=[
                "identify",
                "connections",
            ],
        )
        authorization_url, state = discord_oauth.authorization_url("https://discord.com/oauth2/authorize")

        with self.bot.db as db:
            db['oauth_states'] = db.get('oauth_states', {})
            db['oauth_states'][str(ctx.author.id)] = state
            db.sync()

        # Store the state in the user's session or database
        await ctx.respond(f"Please authorize the application by clicking [here]({authorization_url}).", ephemeral=True)


def setup(bot: discord.Bot):
    bot.add_cog(GitHubCommandsCog(bot=bot))
