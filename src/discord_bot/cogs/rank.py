# standard imports
import os
from typing import Union

# lib imports
import discord
from discord import option
from discord.ext import commands, tasks

# local imports
from src.common.rank import RankSystem
from src.common import globals


class RankCog(discord.Cog):
    """
    Discord cog for the rank system functionality.
    """

    def __init__(self, bot):
        self.bot = bot
        self.rank_system = RankSystem(bot=self.bot)
        self.active_users = set()  # Track active users in the current minute
        self.xp_award_task.start()

        # Schedule auto-migration after bot is ready
        bot.loop.create_task(self.auto_migrate_mee6())

    def cog_unload(self):
        self.xp_award_task.cancel()

    @tasks.loop(minutes=1)
    async def xp_award_task(self):
        """
        Task that runs every minute to award XP to active users.
        """
        if not self.active_users:
            return

        for user in self.active_users:
            result = self.rank_system.award_xp(
                platform='discord',
                user=user,
            )
            if result and result['level_up']:
                try:
                    # Send level up message in designated channel
                    channel_id = os.getenv('DISCORD_LEVEL_UP_CHANNEL_ID')
                    if channel_id:
                        channel = self.bot.get_channel(int(channel_id))
                        if channel:
                            new_level = result['level']
                            embed = discord.Embed(
                                title="🎉 Level Up!",
                                description=f"{user.mention} has reached **Level {new_level}**!",
                                color=discord.Color.gold(),
                            )
                            embed.set_thumbnail(url=user.display_avatar.url)
                            await channel.send(embed=embed)
                except Exception as e:
                    print(f"Error handling level up notification: {e}")

        # Clear the set for the next minute
        self.active_users.clear()

    @xp_award_task.before_loop
    async def before_xp_award(self):
        """
        Wait until the bot is ready before starting the task.
        """
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message):
        """
        Listen for messages to track active users.

        Parameters
        ----------
        message : discord.Message
            The message object containing the message data.
        """
        if message.author.bot:
            return

        # Add user object to active users set
        self.active_users.add(message.author)

    async def reddit_user_autocomplete(self, ctx: discord.AutocompleteContext) -> list[str]:
        """
        Autocomplete function for Reddit usernames.

        Parameters
        ----------
        ctx : discord.AutocompleteContext
            The context of the autocomplete request.

        Returns
        -------
        list
            List of Reddit usernames matching the current input.
        """
        current = ctx.value or ""

        if not globals.REDDIT_BOT:
            return []

        try:
            reddit_users = self.rank_system.db.get_community_users(
                platform='reddit',
                community_id=globals.REDDIT_BOT.subreddit.id,
                search=current,
            )

            # Extract usernames from user objects
            users = [user.get('username', '') for user in reddit_users[:25] if user.get('username')]

            return users
        except Exception:
            return []

    @discord.slash_command(name="rank", description="Check your rank or another user's rank")
    @option(
        name="discord_user",
        description="Discord user to check rank for",
        required=False,
        type=discord.Member,
    )
    @option(
        name="reddit_user",
        description="Reddit username to check rank for",
        required=False,
        autocomplete=reddit_user_autocomplete,
        type=discord.SlashCommandOptionType.string,
    )
    async def rank(
            self,
            ctx,
            discord_user: discord.Member = None,
            reddit_user: str = None
    ):
        """
        Command to check a user's rank on either Discord or Reddit.

        Parameters
        ----------
        ctx : discord.ApplicationContext
            The context of the command.
        discord_user : discord.Member, optional
            The Discord user to check rank for. If not provided, defaults to the command invoker.
        reddit_user : str, optional
            The Reddit username to check rank for. If not provided, will check the Discord user.
        """
        if reddit_user:
            target_user = globals.REDDIT_BOT.fetch_user(name=reddit_user)
            if not target_user:
                await ctx.respond(f"Reddit user '{reddit_user}' not found.", ephemeral=True)
                return
            platform_name = "Reddit"
            user_data = self.rank_system.get_rank_data(
                platform='reddit',
                user=target_user,
                create_if_not_exists=False,
            )
            rank_position = self.rank_system.get_user_rank_position(
                platform='reddit',
                user=target_user,
            )
            display_name = f"u/{reddit_user}"
            avatar_url = target_user.icon_img
            color = discord.Color.orange()  # Reddit's color
        else:
            target_user = discord_user or ctx.author
            platform_name = "Discord"
            user_data = self.rank_system.get_rank_data(
                platform='discord',
                user=target_user,
                create_if_not_exists=False,
            )
            rank_position = self.rank_system.get_user_rank_position(
                platform='discord',
                user=target_user,
            )
            display_name = target_user.display_name
            avatar_url = target_user.display_avatar.url
            color = target_user.color if hasattr(target_user, 'color') else discord.Color.blue()

        if rank_position is None:
            await ctx.respond(f"{platform_name} user '{display_name}' not found in the rank system.", ephemeral=True)
            return

        # Calculate level data
        level = self.rank_system.calculate_level(xp=user_data['xp'])
        current_xp = user_data['xp']
        xp_for_current = self.rank_system.calculate_xp_for_level(level=level)
        xp_for_next = self.rank_system.calculate_xp_for_level(level=level + 1)

        # Calculate progress bar
        progress = (current_xp - xp_for_current) / (xp_for_next - xp_for_current) if xp_for_next > xp_for_current else 0
        progress_bar_length = 10
        filled_bars = round(progress_bar_length * progress)
        progress_bar = f"{'▰' * filled_bars}{'▱' * (progress_bar_length - filled_bars)}"

        # Create embed
        embed = discord.Embed(
            title=f"{display_name}'s {platform_name} Rank",
            timestamp=discord.utils.utcnow(),
            color=color
        )

        if avatar_url:
            embed.set_thumbnail(url=avatar_url)

        embed.add_field(name="Rank", value=f"#{rank_position}", inline=True)
        embed.add_field(name="Level", value=str(level), inline=True)
        embed.add_field(name="XP", value=f"{current_xp:,}", inline=True)
        embed.add_field(
            name=f"Progress to Level {level + 1}",
            value=f"{progress_bar} {round(progress * 100)}%\n"
                  f"{current_xp - xp_for_current:,}/{xp_for_next - xp_for_current:,} XP",
            inline=False
        )

        embed.add_field(
            name="Messages",
            value=f"{user_data.get('message_count', 0):,}",
            inline=True
        )

        await ctx.respond(embed=embed)

    async def build_leaderboard_embed(self, platform, leaderboard_data, page, total_pages, total_users, ctx):
        """Build the leaderboard embed with improved aesthetics."""
        platform_color = discord.Color.blurple() if platform == "discord" else discord.Color.orange()

        embed = discord.Embed(
            title=f"🏆 {platform.capitalize()} XP Leaderboard",
            description="",
            timestamp=discord.utils.utcnow(),
            color=platform_color
        )

        # Add server icon if available
        if platform == "discord" and ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        elif platform == "reddit" and globals.REDDIT_BOT.subreddit.community_icon:
            embed.set_thumbnail(url=globals.REDDIT_BOT.subreddit.community_icon)

        # Emojis for top ranks
        medal_emojis = [
            "🥇",
            "🥈",
            "🥉",
            ":four:",
            ":five:",
            ":six:",
            ":seven:",
            ":eight:",
            ":nine:",
            ":keycap_ten:",
        ]
        top_positions = len(medal_emojis)

        # Build leaderboard content
        leaderboard_text = ""
        offset = (page - 1) * 10

        for i, entry in enumerate(leaderboard_data, start=1):
            rank_num = offset + i

            # Get appropriate medal or number
            if rank_num <= top_positions:
                rank_display = medal_emojis[rank_num-1]
            else:
                rank_display = f"`#{rank_num}`"

            try:
                if platform == "discord":
                    user = await self.bot.fetch_user(entry['user_id'])
                    username = user.display_name if user else f"User {entry['user_id']}"
                    if user:
                        username = f"**{username}**"
                else:
                    username = f"**u/{entry.get('username', f'User {entry['user_id']}')}**"
            except Exception:
                username = f"**{entry.get('username', f'User {entry['user_id']}')}**"

            level = self.rank_system.calculate_level(xp=entry['xp'])

            # Progress bar for current level
            current_level_xp = self.rank_system.calculate_xp_for_level(level)
            next_level_xp = self.rank_system.calculate_xp_for_level(level + 1)
            progress = (entry['xp'] - current_level_xp) / (next_level_xp - current_level_xp) \
                if next_level_xp > current_level_xp else 0

            progress_bar_length = 10
            filled_bars = round(progress_bar_length * progress)
            progress_bar = f"{'▰' * filled_bars}{'▱' * (progress_bar_length - filled_bars)}"

            leaderboard_text += (
                f"{rank_display} {username}\n"
                f"Lvl {level} | XP: {entry['xp']:,} | Messages: {entry.get('message_count', 0):,}\n"
                f"{progress_bar} {int(progress*100)}%\n"
            )

            # Add decorative separator between entries
            if i < len(leaderboard_data):
                leaderboard_text += "┄┄┄┄┄┄┄┄┄┄┄┄\n"

            embed.description = leaderboard_text

            # Add footer
            embed.set_footer(text=f"Page {page}/{total_pages} • {total_users:,} total ranked users")

        return embed

    def create_leaderboard_buttons(self, page, total_pages, platform):
        """Create navigation buttons for the leaderboard."""
        view = discord.ui.View(timeout=300)  # 5 minutes timeout

        # First page button
        first_button = discord.ui.Button(
            emoji="⏮️",
            style=discord.ButtonStyle.gray,
            disabled=(page == 1),
            custom_id=f"leaderboard:{platform}:first:{page}"  # Make unique with button type
        )
        first_button.callback = lambda i: self.handle_leaderboard_button(i, platform, 1)

        # Previous page button
        prev_button = discord.ui.Button(
            emoji="◀️",
            style=discord.ButtonStyle.gray,
            disabled=(page == 1),
            custom_id=f"leaderboard:{platform}:prev:{page}"  # Make unique with button type
        )
        prev_button.callback = lambda i: self.handle_leaderboard_button(i, platform, max(1, page-1))

        # Page indicator (not clickable)
        page_indicator = discord.ui.Button(
            label=f"{page}/{total_pages}",
            style=discord.ButtonStyle.gray,
            disabled=True,
            custom_id=f"leaderboard:{platform}:indicator:{page}"  # Make unique with page number
        )

        # Next page button
        next_button = discord.ui.Button(
            emoji="▶️",
            style=discord.ButtonStyle.gray,
            disabled=(page == total_pages),
            custom_id=f"leaderboard:{platform}:next:{page}"  # Make unique with button type
        )
        next_button.callback = lambda i: self.handle_leaderboard_button(i, platform, min(total_pages, page+1))

        # Last page button
        last_button = discord.ui.Button(
            emoji="⏭️",
            style=discord.ButtonStyle.gray,
            disabled=(page == total_pages),
            custom_id=f"leaderboard:{platform}:last:{page}"  # Make unique with button type
        )
        last_button.callback = lambda i: self.handle_leaderboard_button(i, platform, total_pages)

        view.add_item(first_button)
        view.add_item(prev_button)
        view.add_item(page_indicator)
        view.add_item(next_button)
        view.add_item(last_button)

        return view

    async def get_leaderboard_data(
            self,
            platform: str,
            community_id: Union[int, str],
            page: int = 1,
            per_page: int = 10,
    ):
        """Get all necessary leaderboard data for the given page."""
        offset = (page - 1) * per_page

        leaderboard_data = self.rank_system.get_leaderboard(
            platform=platform,
            community_id=community_id,
            limit=per_page,
            offset=offset,
        )

        # Get total users for pagination
        total_users = len(self.rank_system.db.get_community_users(
            platform=platform,
            community_id=community_id
        ))
        total_pages = max(1, (total_users + per_page - 1) // per_page)

        return leaderboard_data, total_users, total_pages

    @discord.slash_command(name="leaderboard", description="View the server's XP leaderboard")
    @option(
        name="platform",
        description="Platform to view the leaderboard for",
        required=False,
        choices=["discord", "reddit"],
        default="discord",
        type=str,
    )
    @option(
        name="page",
        description="Page number",
        required=False,
        type=int,
        min_value=1,
        default=1
    )
    async def leaderboard(self, ctx, platform: str = "discord", page: int = 1):
        """Command to view the server leaderboard with pagination."""
        await ctx.defer(ephemeral=False)

        communities = {
            'discord': ctx.guild.id,
            'reddit': globals.REDDIT_BOT.subreddit.id if globals.REDDIT_BOT else None,
        }

        community_id = communities.get(platform)
        if not community_id:
            await ctx.respond(f"No community ID found for platform: {platform}")
            return

        # Get leaderboard data and pagination info
        leaderboard_data, total_users, total_pages = await self.get_leaderboard_data(
            platform=platform,
            community_id=community_id,
            page=page,
        )

        if not leaderboard_data:
            await ctx.respond("No leaderboard data available.")
            return

        # Create the embed and buttons
        embed = await self.build_leaderboard_embed(
            platform=platform,
            leaderboard_data=leaderboard_data,
            page=page,
            total_pages=total_pages,
            total_users=total_users,
            ctx=ctx,
        )
        view = self.create_leaderboard_buttons(
            page=page,
            total_pages=total_pages,
            platform=platform,
        )

        await ctx.respond(embed=embed, view=view)

    async def handle_leaderboard_button(self, interaction: discord.Interaction, platform: str, page: int):
        """Handle pagination button clicks for the leaderboard."""
        await interaction.response.defer()

        communities = {
            'discord': interaction.guild.id,
            'reddit': globals.REDDIT_BOT.subreddit.id if globals.REDDIT_BOT else None,
        }

        community_id = communities.get(platform)
        if not community_id:
            await interaction.edit_original_response(content="Could not determine community ID")
            return

        # Get leaderboard data and pagination info
        leaderboard_data, total_users, total_pages = await self.get_leaderboard_data(
            platform=platform,
            community_id=community_id,
            page=page,
        )

        if not leaderboard_data:
            await interaction.edit_original_response(content="No leaderboard data available.")
            return

        # Create the embed and buttons
        embed = await self.build_leaderboard_embed(
            platform=platform,
            leaderboard_data=leaderboard_data,
            page=page,
            total_pages=total_pages,
            total_users=total_users,
            ctx=interaction,
        )
        view = self.create_leaderboard_buttons(
            page=page,
            total_pages=total_pages,
            platform=platform,
        )

        await interaction.edit_original_response(embed=embed, view=view)

    async def auto_migrate_mee6(self):
        """
        Automatically migrate Mee6 data when the bot starts,
        but only if it hasn't already been migrated.
        """
        await self.bot.wait_until_ready()

        # Process each guild the bot is in
        for guild in self.bot.guilds:
            # Check if migration already done
            migration_status = self.rank_system.get_migration_status(
                platform='discord',
                community_id=guild.id,
                source_id=guild.id,
            )
            if migration_status:
                print(f"Migration already completed for guild: {guild.name} ({guild.id})")
                continue  # Skip if already migrated

            try:
                print(f"Starting automatic Mee6 migration for guild: {guild.name} ({guild.id})")
                result = await self.rank_system.migrate_from_mee6(guild_id=guild.id)

                # Save migration status
                self.rank_system.set_migration_completed(
                    platform='discord',
                    community_id=guild.id,
                    source_id=guild.id,
                    stats=result,
                )

                print(f"Completed Mee6 migration for {guild.name}: {result['total_processed']} users processed")

                # Optional: Notify in a system channel or log channel
                system_channel = guild.system_channel
                if system_channel and system_channel.permissions_for(guild.me).send_messages:
                    embed = discord.Embed(
                        title="Rank System Initialized",
                        description=f"Successfully migrated {result['total_processed']} users from Mee6!",
                        timestamp=discord.utils.utcnow(),
                        color=discord.Color.green(),
                    )
                    embed.add_field(name="New Users", value=str(result['new_users']), inline=True)
                    embed.add_field(name="Updated Users", value=str(result['updated_users']), inline=True)

                    try:
                        await system_channel.send(embed=embed)
                    except discord.HTTPException:
                        pass  # Silently fail if can't send

            except Exception as e:
                print(f"Error during automatic Mee6 migration for guild {guild.id}: {e}")


def setup(bot):
    bot.add_cog(RankCog(bot))
