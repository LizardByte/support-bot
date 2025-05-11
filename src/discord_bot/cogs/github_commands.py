# standard imports
from datetime import datetime, timedelta, UTC
import os

# lib imports
import discord
from requests_oauthlib import OAuth2Session

# local imports
from src.common.common import colors
from src.common import sponsors


link_github_platform_description = 'Platform to link'  # hack for flake8 F722
link_github_platform_choices = [  # hack for flake8 F821
    "discord",
    "github",
]


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

        embed = discord.Embed(title="GitHub Sponsors", color=colors['green'], description=message)

        await ctx.respond(embed=embed, ephemeral=True)

    @discord.slash_command(
        name="link_github",
        description="Validate GitHub sponsor status"
    )
    async def link_github(
            self,
            ctx: discord.ApplicationContext,
            platform: discord.Option(
                str,
                description=link_github_platform_description,
                choices=link_github_platform_choices,
                required=True,
            ),
    ):
        """
        Link Discord account with GitHub account.

        This works by authenticating to GitHub or to Discord and checking the user's "GitHub" connected account status.

        User to login via OAuth2.
        If the Discord option is selected, then check if their connected GitHub account is a sponsor of the project.

        Parameters
        ----------
        ctx : discord.ApplicationContext
            Request message context.
        platform : str
            Platform to link.
        """
        platform_map = {
            'discord': {
                'auth_url': "https://discord.com/api/oauth2/authorize",
                'client_id': os.environ['DISCORD_CLIENT_ID'],
                'redirect_uri': os.environ['DISCORD_REDIRECT_URI'],
                'scope': [
                    "identify",
                    "connections",
                ],
            },
            'github': {
                'auth_url': "https://github.com/login/oauth/authorize",
                'client_id': os.environ['GITHUB_CLIENT_ID'],
                'redirect_uri': os.environ['GITHUB_REDIRECT_URI'],
                'scope': [
                    "read:user",
                ],
            },
        }

        auth = OAuth2Session(
            client_id=platform_map[platform]['client_id'],
            redirect_uri=platform_map[platform]['redirect_uri'],
            scope=platform_map[platform]['scope'],
        )
        authorization_url, state = auth.authorization_url(platform_map[platform]['auth_url'])

        # Store the state in the user's session or database
        with self.bot.db as db:
            db['oauth_states'] = db.get('oauth_states', {})
            db['oauth_states'][str(ctx.author.id)] = state
            db.sync()

        response = await ctx.respond(
            f"Please authorize the application by clicking [here]({authorization_url}).",
            ephemeral=True,
        )

        now = datetime.now(UTC)
        db = self.bot.ephemeral_db
        db['github_cache_context'] = db.get('github_cache_context', {})

        # if there is a current context, update the original response on discord
        if str(ctx.author.id) in db['github_cache_context']:
            await self.bot.async_update_cached_message(
                author_id=ctx.author.id,
                reason='duplicate',
            )

        db['github_cache_context'][str(ctx.author.id)] = {
            'created_at': now,
            'expires_at': now + timedelta(seconds=300),
            'response': response,
        }


def setup(bot: discord.Bot):
    bot.add_cog(GitHubCommandsCog(bot=bot))
