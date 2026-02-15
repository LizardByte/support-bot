# standard imports
from datetime import datetime, UTC
import math
import random
import threading
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

# Global migration lock to prevent concurrent migrations
MIGRATION_LOCK = threading.Lock()


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
        # Acquire migration lock to prevent concurrent migrations
        with MIGRATION_LOCK:
            return self._do_reddit_migration(reddit_bot, reddit_db, community_id)

    def _process_reddit_item(
            self,
            reddit_bot,
            item: dict,
            item_type: str,
            user_xp_map: dict,
    ) -> Tuple[bool, bool]:
        """
        Process a single Reddit submission or comment.

        Parameters
        ----------
        reddit_bot
            Reddit bot instance
        item : dict
            Submission or comment data
        item_type : str
            'submission' or 'comment'
        user_xp_map : dict
            Map of user_id to XP stats

        Returns
        -------
        Tuple[bool, bool]
            (success, skipped) - True if processed successfully, True if skipped
        """
        author_name = item.get('author')
        if not author_name or author_name == "[deleted]":
            return False, True

        try:
            author = reddit_bot.fetch_user(name=author_name)
        except Exception as e:
            print(f"Error fetching author '{author_name}' for {item_type}: {type(e).__name__}: {e}")
            return False, True

        # Skip items without valid author
        if not author or not hasattr(author, 'id'):
            print(f"Invalid author object for '{author_name}', skipping {item_type}")
            return False, True

        # Award random XP in range
        xp_gain = random.randint(150, 250)

        if author.id not in user_xp_map:
            user_xp_map[author.id] = {'xp': 0, 'submissions': 0, 'comments': 0, 'name': author.name}

        user_xp_map[author.id]['xp'] += xp_gain
        if item_type == 'submission':
            user_xp_map[author.id]['submissions'] += 1
        else:
            user_xp_map[author.id]['comments'] += 1

        return True, False

    def _update_reddit_rank_database(
            self,
            community_id: str,
            user_xp_map: dict,
    ) -> Tuple[int, int]:
        """
        Update the rank database with accumulated XP.

        Parameters
        ----------
        community_id : str
            Subreddit ID
        user_xp_map : dict
            Map of user_id to XP stats

        Returns
        -------
        Tuple[int, int]
            (new_users, updated_users)
        """
        new_users = 0
        updated_users = 0
        total_users = len(user_xp_map)

        print(f"Updating {total_users} users in rank database")

        with self.db as db:
            table = db.table('reddit_users')

            # Build a lookup map of existing users for faster access
            print("Building lookup map of existing users...")
            existing_users_map = {}
            for item in table.all():
                key = (item.get('user_id'), item.get('community_id'))
                existing_users_map[key] = item
            print(f"Found {len(existing_users_map)} existing users")

            # Process each user
            processed = 0
            for user_id, stats in user_xp_map.items():
                key = (user_id, community_id)
                existing = existing_users_map.get(key)

                if existing and existing.get('xp', 0) > 0:
                    updated_users += 1
                else:
                    new_users += 1

                # Prepare user data
                user_data = {
                    'user_id': user_id,
                    'community_id': community_id,
                    'xp': stats['xp'],
                    'message_count': stats['submissions'] + stats['comments'],
                    'submission_count': stats['submissions'],
                    'comment_count': stats['comments'],
                    'username': stats['name'],
                    'reddit_import_date': datetime.now(UTC).isoformat(),
                }

                # Update or insert
                if existing:
                    table.update(user_data, doc_ids=[existing.doc_id])
                else:
                    table.insert(user_data)

                processed += 1
                # Print progress every 50 users
                if processed % 50 == 0:
                    print(f"Progress: {processed}/{total_users} users processed")

            print(f"Finished updating {total_users} users")

        return new_users, updated_users

    def _do_reddit_migration(
            self,
            reddit_bot,
            reddit_db,
            community_id: str,
    ) -> Dict[str, Union[int, str]]:
        """Internal method that performs the actual Reddit migration."""
        total_submissions = 0
        total_comments = 0
        skipped_submissions = 0
        skipped_comments = 0
        user_xp_map = {}  # Maps user_id to accumulated XP

        original_git_enabled = database.GIT_ENABLED
        database.GIT_ENABLED = False  # Disable Git for this operation

        print("Starting Reddit ranks migration")

        try:
            # Process submissions
            with reddit_db as db:
                submissions_table = db.table('submissions')

                print(f"Processing {len(submissions_table.all())} submissions")
                for submission in submissions_table.all():
                    try:
                        success, skipped = self._process_reddit_item(
                            reddit_bot, submission, 'submission', user_xp_map
                        )
                        if success:
                            total_submissions += 1
                        elif skipped:
                            skipped_submissions += 1
                    except Exception as e:
                        author_name = submission.get('author', 'unknown')
                        print(f"Unexpected error processing submission by '{author_name}': {type(e).__name__}: {e}")
                        skipped_submissions += 1

                # Process comments
                comments_table = db.table('comments')

                print(f"Processing {len(comments_table.all())} comments")
                for comment in comments_table.all():
                    try:
                        success, skipped = self._process_reddit_item(
                            reddit_bot, comment, 'comment', user_xp_map
                        )
                        if success:
                            total_comments += 1
                        elif skipped:
                            skipped_comments += 1
                    except Exception as e:
                        author_name = comment.get('author', 'unknown')
                        print(f"Unexpected error processing comment by '{author_name}': {type(e).__name__}: {e}")
                        skipped_comments += 1

            # Update the rank database
            new_users, updated_users = self._update_reddit_rank_database(community_id, user_xp_map)

        except Exception as e:
            print(f"Error during Reddit migration: {type(e).__name__}: {e}")
            database.GIT_ENABLED = original_git_enabled
            raise

        # Restore original Git state and force one final sync
        database.GIT_ENABLED = original_git_enabled
        self.db.sync()

        stats = {
            'total_users': len(user_xp_map),
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
        import asyncio

        # Use async-friendly locking
        loop = asyncio.get_event_loop()

        # Acquire lock in a thread-safe way for async
        await loop.run_in_executor(None, MIGRATION_LOCK.acquire)

        try:
            return await self._do_mee6_migration(guild_id)
        finally:
            MIGRATION_LOCK.release()

    async def _fetch_mee6_page(
            self,
            session: aiohttp.ClientSession,
            guild_id: int,
            page: int,
    ) -> Optional[list]:
        """
        Fetch a single page of Mee6 data.

        Parameters
        ----------
        session : aiohttp.ClientSession
            HTTP session
        guild_id : int
            Discord guild ID
        page : int
            Page number to fetch

        Returns
        -------
        Optional[list]
            List of player data, or None if fetch failed
        """
        url = f"https://mee6.xyz/api/plugins/levels/leaderboard/{guild_id}?page={page}"
        print(f"Fetching Mee6 data from: {url}")

        try:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    print(f"Received status code {response.status}, stopping migration")
                    return None

                data = await response.json()

                if not data.get('players') or len(data['players']) == 0:
                    print("No more players found, stopping migration")
                    return None

                player_count = len(data['players'])
                print(f"Processing {player_count} players from page {page}")
                return data['players']

        except aiohttp.ClientError as e:
            print(f"HTTP error during migration: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error during migration: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _process_mee6_batch(
            self,
            guild_id: int,
            batch: list,
    ) -> Tuple[int, int]:
        """
        Process a batch of Mee6 user updates.

        Parameters
        ----------
        guild_id : int
            Discord guild ID
        batch : list
            List of user update dictionaries

        Returns
        -------
        Tuple[int, int]
            (new_users, updated_users)
        """
        new_users = 0
        updated_users = 0

        with self.db as db:
            table = db.table('discord_users')

            # Build a lookup map of existing users in this batch
            existing_users_map = {}
            for item in table.all():
                if item.get('community_id') == guild_id:
                    existing_users_map[item.get('user_id')] = item

            for user_update in batch:
                user_id = user_update['user_id']
                existing = existing_users_map.get(user_id)

                if existing and existing.get('xp', 0) > 0:
                    updated_users += 1
                else:
                    new_users += 1

                # Prepare user data
                user_data = {
                    'user_id': user_id,
                    'community_id': guild_id,
                    'xp': user_update['xp'],
                    'message_count': user_update['message_count'],
                    'username': user_update['username'],
                    'mee6_import_date': user_update['mee6_import_date'],
                }

                # Update or insert
                if existing:
                    table.update(user_data, doc_ids=[existing.doc_id])
                else:
                    table.insert(user_data)

        return new_users, updated_users

    async def _do_mee6_migration(self, guild_id: int) -> Dict[str, Union[int, str]]:
        """Internal method that performs the actual Mee6 migration."""
        page = 0
        total_users = 0
        new_users = 0
        updated_users = 0
        batch_updates = []  # Collect all updates before applying

        original_git_enabled = database.GIT_ENABLED
        database.GIT_ENABLED = False  # Disable Git for this operation

        async with aiohttp.ClientSession() as session:
            while True:
                players = await self._fetch_mee6_page(session, guild_id, page)
                if players is None:
                    break

                for player in players:
                    total_users += 1
                    user_id = int(player['id'])

                    # Collect update data without writing yet
                    user_update = {
                        'user_id': user_id,
                        'xp': player['xp'],
                        'message_count': player.get('message_count', 0),
                        'username': player.get('username', f"User {user_id}"),
                        'mee6_import_date': datetime.now(UTC).isoformat(),
                    }
                    batch_updates.append(user_update)

                page += 1

        # Now apply all updates in batches
        print(f"Applying {len(batch_updates)} user updates in batches")
        BATCH_SIZE = 100

        for i in range(0, len(batch_updates), BATCH_SIZE):
            batch = batch_updates[i:i+BATCH_SIZE]
            batch_new, batch_updated = self._process_mee6_batch(guild_id, batch)
            new_users += batch_new
            updated_users += batch_updated
            print(f"Completed batch {i//BATCH_SIZE + 1}/{(len(batch_updates)-1)//BATCH_SIZE + 1}")

        # Restore original Git state and force one final sync
        database.GIT_ENABLED = original_git_enabled
        self.db.sync()

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
