# standard imports
from typing import List, Optional, Union

# local imports
from src.common.database import Database


class RankDatabase(Database):
    """
    Specialized database for managing rank data across platforms.
    Uses a flatter structure with platform-specific tables (discord_users, reddit_users).
    Each entry represents a unique user in a specific community.
    """

    def __init__(self, **kwargs):
        """
        Initialize the rank database.
        """
        kwargs['db_name'] = 'ranks'
        super().__init__(**kwargs)
        self._ensure_tables()

    def _ensure_tables(self):
        """
        Ensure that the necessary tables exist in the database.
        """
        with self as db:
            # Create platform-specific user tables while preserving existing data
            tables_to_ensure = [
                'discord_users',
                'reddit_users',
                'migrations',
            ]

            for table_name in tables_to_ensure:
                if table_name not in db.tables():
                    db.table(table_name)

    def get_community_users(
            self,
            platform: str,
            community_id: Union[int, str],
            search: Optional[str] = None,
    ) -> List[dict]:
        """
        Get all users in a specific community for a given platform.

        Parameters
        ----------
        platform : str
            Platform identifier ('discord' or 'reddit')
        community_id : Union[int, str]
            Community identifier (guild_id for Discord, subreddit_id for Reddit)
        search : Optional[str]
            Optional search string to filter users by username (case-insensitive)

        Returns
        -------
        List[dict]
            List of user data in the specified community
        """
        if platform not in ['discord', 'reddit']:
            raise ValueError(f"Invalid platform: {platform}")

        table_name = f"{platform}_users"

        with self as db:
            table = db.table(table_name)
            users = [dict(item) for item in table.all() if item.get('community_id') == community_id]

            # Apply search filter if provided
            if search and search.strip():
                search_lower = search.lower().strip()
                users = [
                    user for user in users
                    if user.get('username') and search_lower in user.get('username', '').lower()
                ]

            # sort users alphabetically by username
            users.sort(key=lambda x: x.get('username', '').lower())

            return users

    def get_user_data(
            self,
            platform: str,
            community_id: Union[int, str],
            user_id: Union[int, str],
            create_if_not_exists: bool = False,
    ) -> dict:
        """
        Get user rank data for a specific platform, community, and user.

        Parameters
        ----------
        platform : str
            Platform identifier ('discord' or 'reddit')
        community_id : Union[int, str]
            Community identifier (guild_id for Discord, subreddit_id for Reddit)
        user_id : Union[int, str]
            User identifier
        create_if_not_exists : bool
            Whether to create a new user entry if it doesn't exist

        Returns
        -------
        dict
            User rank data or a new user entry
        """
        if platform not in ['discord', 'reddit']:
            raise ValueError(f"Invalid platform: {platform}")

        table_name = f"{platform}_users"

        with self as db:
            table = db.table(table_name)

            # Find user in the specific community
            user_data = None
            for item in table.all():
                if item.get('user_id') == user_id and item.get('community_id') == community_id:
                    user_data = item
                    break

            # Create new user data if not found
            if not user_data and create_if_not_exists:
                user_data = {
                    'user_id': user_id,
                    'community_id': community_id,
                    'xp': 0,
                    'message_count': 0,
                    'last_activity': 0,
                }
                doc_id = table.insert(user_data)
                # Retrieve the document with its doc_id
                user_data = table.get(doc_id=doc_id)

            return user_data

    def update_user_data(
            self,
            platform: str,
            community_id: Union[int, str],
            user_id: Union[int, str],
            data: dict,
    ) -> dict:
        """
        Update user rank data.

        Parameters
        ----------
        platform : str
            Platform identifier ('discord' or 'reddit')
        community_id : Union[int, str]
            Community identifier (guild_id or subreddit_id)
        user_id : Union[int, str]
            User identifier
        data : dict
            New user data

        Returns
        -------
        dict
            Updated user data
        """
        if platform not in ['discord', 'reddit']:
            raise ValueError(f"Invalid platform: {platform}")

        table_name = f"{platform}_users"

        with self as db:
            table = db.table(table_name)

            # Ensure community_id and user_id are in the data
            data['user_id'] = user_id
            data['community_id'] = community_id

            # Find existing user data
            existing = None
            for item in table.all():
                if item.get('user_id') == user_id and item.get('community_id') == community_id:
                    existing = item
                    break

            if existing:
                # Update existing document
                table.update(data, doc_ids=[existing.doc_id])
                updated = table.get(doc_id=existing.doc_id)
            else:
                # Insert new document
                doc_id = table.insert(data)
                updated = table.get(doc_id=doc_id)

            return updated

    def get_leaderboard(
            self,
            platform: str,
            community_id: Union[int, str],
            limit: int = 100,
            offset: int = 0,
    ) -> List[dict]:
        """
        Get the leaderboard for a specific platform and community.

        Parameters
        ----------
        platform : str
            Platform identifier ('discord' or 'reddit')
        community_id : Union[int, str]
            Community identifier (guild_id or subreddit_id)
        limit : int
            Maximum number of entries to return
        offset : int
            Number of entries to skip

        Returns
        -------
        List[dict]
            List of user data ordered by XP (descending)
        """
        if platform not in ['discord', 'reddit']:
            raise ValueError(f"Invalid platform: {platform}")

        table_name = f"{platform}_users"

        with self as db:
            table = db.table(table_name)

            # Filter users by community
            community_users = []
            for item in table.all():
                if item.get('community_id') == community_id:
                    # Convert to dict to avoid TinyDB document issues
                    community_users.append(dict(item))

            # Sort by XP (descending)
            sorted_users = sorted(community_users, key=lambda x: x.get('xp', 0), reverse=True)

            # Apply pagination
            end_index = offset + limit
            if end_index > len(sorted_users):
                end_index = len(sorted_users)

            if offset >= len(sorted_users):
                return []

            paginated = sorted_users[offset:end_index]
            return paginated

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
        migration_key = f"{platform}:{community_id}:{source_id}"

        with self as db:
            migrations = db.table('migrations')

            # Find migration record
            for migration in migrations.all():
                if migration.get('migration_key') == migration_key:
                    return migration

            return None

    def set_migration_completed(
            self, platform: str,
            community_id: Union[int, str],
            source_id: Union[int, str],
            stats: dict,
    ) -> dict:
        """
        Mark migration as completed.

        Parameters
        ----------
        platform : str
            Platform identifier ('discord' or 'reddit')
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
        migration_key = f"{platform}:{community_id}:{source_id}"

        with self as db:
            migrations = db.table('migrations')

            migration_data = {
                'migration_key': migration_key,
                'platform': platform,
                'community_id': community_id,
                'source_id': source_id,
                'source_type': stats.get('source_type', 'mee6'),
                'timestamp': stats.get('date', None),
                'stats': stats,
            }

            migrations.insert(migration_data)
            return migration_data
