# standard imports
from datetime import datetime, UTC
import math
import random
import time
from typing import Dict, List, Optional, Tuple, Union

# lib imports
import aiohttp
from discord import User as DiscordUser
from praw.models import Redditor as RedditUser

# local imports
from src.common import database
from src.common import globals
from src.common.rank_database import RankDatabase
from src.discord_bot.bot import Bot


class RankSystem:
    """
    A rank system that tracks user XP and levels across platforms.

    Supports:
    - Discord and Reddit users
    - Random XP gain with cooldowns
    - Migration from Mee6
    """

    def __init__(
            self,
            bot: Bot,
            xp_range: Tuple[int, int] = (15, 25),
            cooldown: int = 60,
    ):
        """
        Initialize the rank system.

        Parameters
        ----------
        bot : Bot
            Discord bot instance
        xp_range : Tuple[int, int]
            Min and max range for random XP gain
        cooldown : int
            Cooldown in seconds between XP gains for the same user
        """
        self.bot = bot
        self.db = RankDatabase()
        self.xp_range = xp_range
        self.cooldown = cooldown
        self.last_activity = {}  # Tracks last activity time for cooldowns

    @staticmethod
    def get_community_id(platform: str, user: Union[DiscordUser, RedditUser]) -> Optional[Union[int, str]]:
        """
        Get the community ID for a user based on platform.

        Parameters
        ----------
        platform : str
            Platform identifier ('discord' or 'reddit')
        user : Union[DiscordUser, RedditUser]
            Discord or Reddit user object

        Returns
        -------
        Union[int, str]
            Community ID (guild_id for Discord, subreddit_id for Reddit)
        """
        if platform == 'discord':
            # For Discord, use the current guild ID
            # In case of DMs, this will be None
            guild = getattr(user, 'guild', None)
            if guild:
                return guild.id

            # For guild members that might not have direct guild attribute
            guild_id = getattr(getattr(user, 'guild_id', None), 'id', None)
            if guild_id:
                return guild_id

            # Fallback
            return None

        elif platform == 'reddit':
            # For Reddit, use the current subreddit ID
            subreddit_id = globals.REDDIT_BOT.subreddit.id
            return subreddit_id

        # Default if platform is unknown
        return 0

    @staticmethod
    def calculate_level(xp: int) -> int:
        """
        Calculate level based on XP.
        Using a similar formula to Mee6.

        Parameters
        ----------
        xp : int
            The user's XP

        Returns
        -------
        int
            The calculated level
        """
        # Formula similar to Mee6: Level = sqrt(XP / some_constant)
        return math.floor(math.sqrt(xp / 100))

    @staticmethod
    def calculate_xp_for_level(level: int) -> int:
        """
        Calculate the minimum XP needed for a given level.

        Parameters
        ----------
        level : int
            The level

        Returns
        -------
        int
            The XP needed for this level
        """
        return level * level * 100

    def get_rank_data(
            self,
            platform: str,
            user: Union[DiscordUser, RedditUser],
            create_if_not_exists: bool = False,
    ) -> dict:
        """
        Get rank data for a user.

        Parameters
        ----------
        platform : str
            Platform identifier (e.g., 'discord', 'reddit')
        user : Union[DiscordUser, RedditUser]
            Discord or Reddit user object
        create_if_not_exists : bool
            If True, create a new user entry if it doesn't exist

        Returns
        -------
        dict
            User rank data
        """
        community_id = self.get_community_id(
            platform=platform,
            user=user,
        )
        user_id = user.id

        print(f"Getting rank data for user {user_id} in community {community_id} on platform {platform}")

        user_data = self.db.get_user_data(
            platform=platform,
            community_id=community_id,
            user_id=user_id,
            create_if_not_exists=create_if_not_exists,
        )

        # Return empty dict if user data doesn't exist and not creating
        if not user_data:
            return {}

        # If user data doesn't exist, create a new entry
        if 'username' not in user_data:
            user_data['username'] = user.name
            self.db.update_user_data(
                platform=platform,
                community_id=community_id,
                user_id=user_id,
                data=user_data,
            )

        return user_data

    def update_rank_data(self, platform: str, user: Union[DiscordUser, RedditUser], data: dict) -> dict:
        """
        Update rank data for a user.

        Parameters
        ----------
        platform : str
            Platform identifier (e.g., 'discord', 'reddit')
        user : Union[DiscordUser, RedditUser]
            Discord or Reddit user object
        data : dict
            New data to update

        Returns
        -------
        dict
            Updated user data
        """
        community_id = self.get_community_id(
            platform=platform,
            user=user,
        )
        user_id = user.id
        return self.db.update_user_data(
            platform=platform,
            community_id=community_id,
            user_id=user_id,
            data=data,
        )

    def award_xp(self, platform: str, user: Union[DiscordUser, RedditUser]) -> Optional[dict]:
        """
        Award XP to a user with cooldown enforcement.

        Parameters
        ----------
        platform : str
            Platform identifier (e.g., 'discord', 'reddit')
        user : Union[DiscordUser, RedditUser]
            Discord or Reddit user object

        Returns
        -------
        Optional[dict]
            Updated user data and level info, or None if on cooldown
        """
        user_id = user.id
        community_id = self.get_community_id(
            platform=platform,
            user=user,
        )
        user_key = f"{platform}:{community_id}:{user_id}"
        current_time = int(time.time())

        # Check cooldown
        if user_key in self.last_activity:
            if current_time - self.last_activity[user_key] < self.cooldown:
                return None  # Still on cooldown

        # Get user data
        user_data = self.get_rank_data(
            platform=platform,
            user=user,
            create_if_not_exists=True,
        )
        old_level = self.calculate_level(xp=user_data['xp'])

        # Award random XP
        xp_gain = random.randint(self.xp_range[0], self.xp_range[1])
        user_data['xp'] += xp_gain
        user_data['message_count'] = user_data.get('message_count', 0) + 1
        user_data['last_activity'] = current_time

        # Update cooldown tracker
        self.last_activity[user_key] = current_time

        # Update database
        updated_data = self.update_rank_data(
            platform=platform,
            user=user,
            data=user_data,
        )

        # Check for level up
        new_level = self.calculate_level(xp=updated_data['xp'])
        level_up = new_level > old_level

        return {
            'user_data': updated_data,
            'xp_gain': xp_gain,
            'level': new_level,
            'level_up': level_up,
            'old_level': old_level
        }

    def get_leaderboard(
            self,
            platform: str,
            user: Optional[Union[DiscordUser, RedditUser]] = None,
            community_id: Optional[Union[int, str]] = None,
            limit: int = 100,
            offset: int = 0,
    ) -> List[dict]:
        """
        Get the leaderboard for a specific platform and community.

        Parameters
        ----------
        platform : str
            Platform identifier (e.g., 'discord', 'reddit')
        user : Optional[Union[DiscordUser, RedditUser]]
            User object to determine community_id if not explicitly provided
        community_id : Optional[Union[int, str]]
            Community identifier (guild_id for Discord, subreddit_id for Reddit)
        limit : int
            Maximum number of entries to return
        offset : int
            Number of entries to skip

        Returns
        -------
        List[dict]
            List of user data ordered by XP (descending)
        """
        # If community_id not provided, try to get it from user
        if not community_id and user:
            community_id = self.get_community_id(
                platform=platform,
                user=user,
            )

        # Default to '0' if still no community_id
        if not community_id:
            community_id = '0'

        leaderboard = self.db.get_leaderboard(
            platform=platform,
            community_id=community_id,
            limit=limit,
            offset=offset,
        )

        # Add rank and level to each entry
        for i, user_data in enumerate(leaderboard, start=offset + 1):
            user_data['rank'] = i
            user_data['level'] = self.calculate_level(xp=user_data.get('xp', 0))

        return leaderboard

    def get_user_rank_position(self, platform: str, user: Union[DiscordUser, RedditUser]) -> Optional[int]:
        """
        Get the exact rank position of a user on the leaderboard without any limits.

        Parameters
        ----------
        platform : str
            Platform identifier (e.g., 'discord', 'reddit')
        user : Union[DiscordUser, RedditUser]
            Discord or Reddit user object

        Returns
        -------
        Optional[int]
            User's position in the leaderboard (1-based index). None if user not found.
        """
        community_id = self.get_community_id(
            platform=platform,
            user=user,
        )
        user_id = user.id

        leaderboard = self.db.get_leaderboard(
            platform=platform,
            community_id=community_id,
            limit=1000000,  # Get all users
        )

        # Find user's position
        for i, entry in enumerate(leaderboard, start=1):
            if entry.get('user_id') == user_id:
                return i

        # If user not found, return None
        return None

    def get_migration_status(
            self,
            platform: str,
            community_id: Union[int, str],
            source_id: Union[int, str],
    ) -> Optional[dict]:
        """
        Check if migration has already been performed for a specific source.

        Parameters
        ----------
        platform : str
            Platform identifier (e.g., 'discord', 'reddit')
        community_id : Union[int, str]
            Community identifier (guild_id or subreddit_id)
        source_id : Union[int, str]
            Source identifier (e.g., guild_id for Mee6)

        Returns
        -------
        Optional[dict]
            Migration record if exists, None otherwise
        """
        return self.db.get_migration_status(
            platform=platform,
            community_id=community_id,
            source_id=source_id,
        )

    def set_migration_completed(
            self,
            platform: str,
            community_id: Union[int, str],
            source_id: Union[int, str],
            stats: dict,
    ) -> dict:
        """
        Mark migration as completed.

        Parameters
        ----------
        platform : str
            Platform identifier (e.g., 'discord', 'reddit')
        community_id : Union[int, str]
            Community identifier (guild_id or subreddit_id)
        source_id : Union[int, str]
            Source identifier (e.g., guild_id for Mee6)
        stats : dict
            Migration statistics

        Returns
        -------
        dict
            Updated migration record
        """
        return self.db.set_migration_completed(
            platform=platform,
            community_id=community_id,
            source_id=source_id,
            stats=stats,
        )

    def migrate_from_reddit_database(
            self,
            reddit_bot,
            reddit_db,
            community_id: str,
    ) -> Dict[str, Union[int, str]]:
        """
        Migrate user data from Reddit database.

        This grants XP for existing submissions and comments in the Reddit database.

        Parameters
        ----------
        reddit_bot
            Reddit bot instance
        reddit_db : Database
            Reddit database instance
        community_id : str
            Subreddit ID

        Returns
        -------
        Dict[str, Union[int, str]]
            Migration statistics
        """
        total_users = 0
        new_users = 0
        updated_users = 0
        total_submissions = 0
        total_comments = 0
        skipped_submissions = 0
        skipped_comments = 0
        user_xp_map = {}  # Maps user_id to accumulated XP

        database.GIT_ENABLED = False  # Disable Git for this operation

        print("Starting Reddit ranks migration")

        try:
            # Process submissions
            with reddit_db as db:
                submissions_table = db.table('submissions')

                print(f"Processing {len(submissions_table.all())} submissions")
                for submission in submissions_table.all():
                    author_name = submission.get('author')
                    if not author_name or author_name == "[deleted]":
                        skipped_submissions += 1
                        continue

                    try:
                        try:
                            author = reddit_bot.fetch_user(name=author_name)
                        except Exception as e:
                            print(f"Error fetching author '{author_name}' for submission: {type(e).__name__}: {e}")
                            skipped_submissions += 1
                            continue

                        # Skip submissions without valid author
                        if not author or not hasattr(author, 'id'):
                            print(f"Invalid author object for '{author_name}', skipping submission")
                            skipped_submissions += 1
                            continue

                        total_submissions += 1

                        # Award random XP in range
                        xp_gain = random.randint(150, 250)

                        if author.id not in user_xp_map:
                            user_xp_map[author.id] = {'xp': 0, 'submissions': 0, 'comments': 0, 'name': author.name}

                        user_xp_map[author.id]['xp'] += xp_gain
                        user_xp_map[author.id]['submissions'] += 1
                    except Exception as e:
                        print(f"Unexpected error processing submission by '{author_name}': {type(e).__name__}: {e}")
                        skipped_submissions += 1
                        continue

                # Process comments
                comments_table = db.table('comments')

                print(f"Processing {len(comments_table.all())} comments")
                for comment in comments_table.all():
                    author_name = comment.get('author')
                    if not author_name or author_name == "[deleted]":
                        skipped_comments += 1
                        continue

                    try:
                        try:
                            author = reddit_bot.fetch_user(name=author_name)
                        except Exception as e:
                            print(f"Error fetching author '{author_name}' for comment: {type(e).__name__}: {e}")
                            skipped_comments += 1
                            continue

                        # Skip comments without valid author
                        if not author or not hasattr(author, 'id'):
                            print(f"Invalid author object for '{author_name}', skipping comment")
                            skipped_comments += 1
                            continue

                        total_comments += 1

                        # Award random XP in range
                        xp_gain = random.randint(150, 250)

                        if author.id not in user_xp_map:
                            user_xp_map[author.id] = {'xp': 0, 'submissions': 0, 'comments': 0, 'name': author.name}

                        user_xp_map[author.id]['xp'] += xp_gain
                        user_xp_map[author.id]['comments'] += 1
                    except Exception as e:
                        print(f"Unexpected error processing comment by '{author_name}': {type(e).__name__}: {e}")
                        skipped_comments += 1
                        continue

            # Now update the rank database with accumulated XP
            total_users = len(user_xp_map)
            print(f"Updating {total_users} users in rank database")

            for user_id, stats in user_xp_map.items():
                database.GIT_ENABLED = False  # set this on every iteration in case it was enabled somewhere else

                # Get existing user data or create new
                user_data = self.db.get_user_data(
                    platform='reddit',
                    community_id=community_id,
                    user_id=user_id,
                    create_if_not_exists=True,
                )

                if user_data.get('xp', 0) > 0:
                    # User already has XP
                    updated_users += 1
                else:
                    # New user or user with no XP
                    new_users += 1

                # Update user with imported data
                user_data['xp'] = stats['xp']
                user_data['message_count'] = stats['submissions'] + stats['comments']
                user_data['submission_count'] = stats['submissions']
                user_data['comment_count'] = stats['comments']
                user_data['username'] = stats['name']
                user_data['reddit_import_date'] = datetime.now(UTC).isoformat()

                self.db.update_user_data(
                    platform='reddit',
                    community_id=community_id,
                    user_id=user_id,
                    data=user_data,
                )

        except Exception as e:
            print(f"Error during Reddit migration: {type(e).__name__}: {e}")
            # Re-raise after enabling Git
            database.GIT_ENABLED = True
            raise

        database.GIT_ENABLED = True  # Re-enable Git after operation

        stats = {
            'total_users': total_users,
            'new_users': new_users,
            'updated_users': updated_users,
            'total_submissions': total_submissions,
            'total_comments': total_comments,
            'skipped_submissions': skipped_submissions,
            'skipped_comments': skipped_comments,
            'community_id': community_id,
            'source_type': 'reddit_database',
            'date': datetime.now(UTC).isoformat(),
        }

        print(f"Reddit migration completed with stats: {stats}")
        return stats

    async def migrate_from_mee6(self, guild_id: int) -> Dict[str, Union[int, str]]:
        """
        Migrate user data from Mee6 API.

        Parameters
        ----------
        guild_id : int
            Discord guild ID to migrate from

        Returns
        -------
        Dict[str, Union[int, str]]
            Migration statistics
        """
        page = 0
        total_users = 0
        new_users = 0
        updated_users = 0

        database.GIT_ENABLED = False  # Disable Git for this operation

        async with aiohttp.ClientSession() as session:
            while True:
                url = f"https://mee6.xyz/api/plugins/levels/leaderboard/{guild_id}?page={page}"
                print(f"Fetching Mee6 data from: {url}")

                try:
                    # Add timeout to prevent hanging
                    async with session.get(url, timeout=10) as response:
                        if response.status != 200:
                            print(f"Received status code {response.status}, stopping migration")
                            break

                        data = await response.json()

                        if not data.get('players') or len(data['players']) == 0:
                            print("No more players found, stopping migration")
                            break

                        player_count = len(data['players'])
                        print(f"Processing {player_count} players from page {page}")

                        for player in data['players']:
                            database.GIT_ENABLED = False  # set this on every loop in case it's updated in another place

                            total_users += 1
                            user_id = int(player['id'])

                            # Get existing user data or create new
                            user_data = self.db.get_user_data(
                                platform='discord',
                                community_id=guild_id,
                                user_id=user_id,
                                create_if_not_exists=True,
                            )

                            if user_data.get('xp', 0) > 0:
                                # User already has XP, skip or update as needed
                                updated_users += 1
                                continue

                            # Update user with imported data
                            user_data['xp'] = player['xp']
                            user_data['message_count'] = player.get('message_count', 0)
                            user_data['username'] = player.get('username', f"User {user_id}")
                            user_data['mee6_import_date'] = datetime.now(UTC).isoformat()

                            self.db.update_user_data('discord', guild_id, user_id, user_data)
                            new_users += 1

                except aiohttp.ClientError as e:
                    print(f"HTTP error during migration: {e}")
                    break
                except Exception as e:
                    print(f"Unexpected error during migration: {e}")
                    break

                page += 1

        database.GIT_ENABLED = True  # Re-enable Git after operation

        stats = {
            'total_processed': total_users,
            'new_users': new_users,
            'updated_users': updated_users,
            'guild_id': guild_id,
            'source_type': 'mee6',
            'date': datetime.now(UTC).isoformat(),
        }

        print(f"Migration completed with stats: {stats}")
        return stats
