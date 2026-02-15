# standard imports
import os
import tempfile
from unittest.mock import patch

# lib imports
import pytest

# local imports
from src.common.rank_database import RankDatabase


class TestRankDatabase:
    @pytest.fixture
    def temp_db_dir(self):
        """Create a temporary directory for test databases."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def rank_db(self, temp_db_dir):
        """Create a RankDatabase instance with temporary database."""
        # Set environment variables for git-free operation
        with patch.dict(os.environ, {}, clear=False):
            # Remove git-related env vars if they exist
            env_patch = {k: v for k, v in os.environ.items()
                        if k not in ['GIT_TOKEN', 'GITHUB_TOKEN', 'GIT_USER_NAME', 'GIT_USER_EMAIL']}
            with patch.dict(os.environ, env_patch, clear=True):
                db = RankDatabase(db_dir=temp_db_dir, use_git=False)
                yield db
                # Ensure database is closed before cleanup
                if hasattr(db, 'tinydb') and db.tinydb is not None:
                    db.tinydb.close()

    def test_init_creates_tables(self, rank_db):
        """Test that initialization creates required tables."""
        with rank_db as db:
            tables = db.tables()
            assert 'discord_users' in tables
            assert 'reddit_users' in tables
            assert 'migrations' in tables

    def test_get_user_data_new_user(self, rank_db):
        """Test getting user data for a new user with create_if_not_exists."""
        user_data = rank_db.get_user_data(
            platform='discord',
            community_id=123456,
            user_id=789,
            create_if_not_exists=True,
        )

        assert user_data is not None
        assert user_data['user_id'] == 789
        assert user_data['community_id'] == 123456
        assert user_data['xp'] == 0
        assert user_data['message_count'] == 0

    def test_get_user_data_existing_user(self, rank_db):
        """Test getting user data for an existing user."""
        # Create user first
        rank_db.get_user_data(
            platform='discord',
            community_id=123456,
            user_id=789,
            create_if_not_exists=True,
        )

        # Retrieve again
        user_data = rank_db.get_user_data(
            platform='discord',
            community_id=123456,
            user_id=789,
            create_if_not_exists=False,
        )

        assert user_data is not None
        assert user_data['user_id'] == 789

    def test_get_user_data_not_found(self, rank_db):
        """Test getting user data when user doesn't exist and create_if_not_exists is False."""
        user_data = rank_db.get_user_data(
            platform='discord',
            community_id=123456,
            user_id=999,
            create_if_not_exists=False,
        )

        assert user_data is None

    def test_update_user_data_existing(self, rank_db):
        """Test updating data for an existing user."""
        # Create user first
        original_data = rank_db.get_user_data(
            platform='discord',
            community_id=123456,
            user_id=789,
            create_if_not_exists=True,
        )

        # Update data
        updated_data = {
            'user_id': 789,
            'community_id': 123456,
            'xp': 500,
            'message_count': 25,
            'username': 'TestUser',
        }

        result = rank_db.update_user_data(
            platform='discord',
            community_id=123456,
            user_id=789,
            data=updated_data,
        )

        assert result['xp'] == 500
        assert result['message_count'] == 25
        assert result['username'] == 'TestUser'

    def test_update_user_data_new_user(self, rank_db):
        """Test updating data creates a new user if it doesn't exist."""
        new_data = {
            'user_id': 999,
            'community_id': 123456,
            'xp': 100,
            'message_count': 5,
        }

        result = rank_db.update_user_data(
            platform='discord',
            community_id=123456,
            user_id=999,
            data=new_data,
        )

        assert result is not None
        assert result['user_id'] == 999
        assert result['xp'] == 100

    def test_get_leaderboard_empty(self, rank_db):
        """Test getting leaderboard when no users exist."""
        leaderboard = rank_db.get_leaderboard(
            platform='discord',
            community_id=123456,
            limit=10,
        )

        assert leaderboard == []

    def test_get_leaderboard_sorted(self, rank_db):
        """Test that leaderboard is sorted by XP descending."""
        # Create users with different XP
        users = [
            {'user_id': 1, 'community_id': 123456, 'xp': 500, 'username': 'User1'},
            {'user_id': 2, 'community_id': 123456, 'xp': 1000, 'username': 'User2'},
            {'user_id': 3, 'community_id': 123456, 'xp': 250, 'username': 'User3'},
        ]

        for user_data in users:
            rank_db.update_user_data(
                platform='discord',
                community_id=123456,
                user_id=user_data['user_id'],
                data=user_data,
            )

        leaderboard = rank_db.get_leaderboard(
            platform='discord',
            community_id=123456,
            limit=10,
        )

        assert len(leaderboard) == 3
        assert leaderboard[0]['xp'] == 1000  # User2
        assert leaderboard[1]['xp'] == 500   # User1
        assert leaderboard[2]['xp'] == 250   # User3

    def test_get_leaderboard_pagination(self, rank_db):
        """Test leaderboard pagination with limit and offset."""
        # Create 5 users
        for i in range(5):
            rank_db.update_user_data(
                platform='discord',
                community_id=123456,
                user_id=i,
                data={
                    'user_id': i,
                    'community_id': 123456,
                    'xp': (i + 1) * 100,
                    'username': f'User{i}',
                },
            )

        # Get first page
        page1 = rank_db.get_leaderboard(
            platform='discord',
            community_id=123456,
            limit=2,
            offset=0,
        )

        assert len(page1) == 2
        assert page1[0]['xp'] == 500  # Highest

        # Get second page
        page2 = rank_db.get_leaderboard(
            platform='discord',
            community_id=123456,
            limit=2,
            offset=2,
        )

        assert len(page2) == 2
        assert page2[0]['xp'] == 300

    def test_get_leaderboard_different_communities(self, rank_db):
        """Test that leaderboard only shows users from specified community."""
        # Create users in different communities
        rank_db.update_user_data(
            platform='discord',
            community_id=111,
            user_id=1,
            data={'user_id': 1, 'community_id': 111, 'xp': 500},
        )
        rank_db.update_user_data(
            platform='discord',
            community_id=222,
            user_id=2,
            data={'user_id': 2, 'community_id': 222, 'xp': 1000},
        )

        # Get leaderboard for community 111
        leaderboard = rank_db.get_leaderboard(
            platform='discord',
            community_id=111,
            limit=10,
        )

        assert len(leaderboard) == 1
        assert leaderboard[0]['community_id'] == 111

    def test_get_community_users_empty(self, rank_db):
        """Test getting community users when none exist."""
        users = rank_db.get_community_users(
            platform='discord',
            community_id=123456,
        )

        assert users == []

    def test_get_community_users(self, rank_db):
        """Test getting all users in a community."""
        # Create users
        for i in range(3):
            rank_db.update_user_data(
                platform='discord',
                community_id=123456,
                user_id=i,
                data={
                    'user_id': i,
                    'community_id': 123456,
                    'xp': i * 100,
                    'username': f'User{i}',
                },
            )

        users = rank_db.get_community_users(
            platform='discord',
            community_id=123456,
        )

        assert len(users) == 3

    def test_get_community_users_search(self, rank_db):
        """Test searching users in a community."""
        # Create users with different names
        users_data = [
            {'user_id': 1, 'community_id': 123456, 'username': 'Alice'},
            {'user_id': 2, 'community_id': 123456, 'username': 'Bob'},
            {'user_id': 3, 'community_id': 123456, 'username': 'Charlie'},
        ]

        for user_data in users_data:
            rank_db.update_user_data(
                platform='discord',
                community_id=123456,
                user_id=user_data['user_id'],
                data=user_data,
            )

        # Search for users containing 'al'
        results = rank_db.get_community_users(
            platform='discord',
            community_id=123456,
            search='al',
        )

        assert len(results) == 1
        assert results[0]['username'] == 'Alice'

    def test_get_community_users_sorted_alphabetically(self, rank_db):
        """Test that community users are sorted alphabetically by username."""
        # Create users in non-alphabetical order
        users_data = [
            {'user_id': 1, 'community_id': 123456, 'username': 'Zebra'},
            {'user_id': 2, 'community_id': 123456, 'username': 'Apple'},
            {'user_id': 3, 'community_id': 123456, 'username': 'Mango'},
        ]

        for user_data in users_data:
            rank_db.update_user_data(
                platform='discord',
                community_id=123456,
                user_id=user_data['user_id'],
                data=user_data,
            )

        users = rank_db.get_community_users(
            platform='discord',
            community_id=123456,
        )

        assert len(users) == 3
        assert users[0]['username'] == 'Apple'
        assert users[1]['username'] == 'Mango'
        assert users[2]['username'] == 'Zebra'

    def test_reddit_platform(self, rank_db):
        """Test operations with Reddit platform."""
        user_data = rank_db.get_user_data(
            platform='reddit',
            community_id='lizardbyte',
            user_id='reddit_user_123',
            create_if_not_exists=True,
        )

        assert user_data is not None
        assert user_data['user_id'] == 'reddit_user_123'
        assert user_data['community_id'] == 'lizardbyte'

    def test_invalid_platform_raises_error(self, rank_db):
        """Test that invalid platform raises ValueError."""
        with pytest.raises(ValueError, match="Invalid platform"):
            rank_db.get_user_data(
                platform='invalid',
                community_id=123456,
                user_id=789,
            )

    def test_get_migration_status_none(self, rank_db):
        """Test getting migration status when none exists."""
        status = rank_db.get_migration_status(
            platform='discord',
            community_id=123456,
            source_id='mee6',
        )

        assert status is None

    def test_set_migration_completed(self, rank_db):
        """Test setting migration as completed."""
        stats = {
            'source_type': 'mee6',
            'total_processed': 100,
            'new_users': 50,
            'date': '2026-01-01T00:00:00+00:00',
        }

        result = rank_db.set_migration_completed(
            platform='discord',
            community_id=123456,
            source_id='mee6_test',
            stats=stats,
        )

        assert result is not None
        assert result['platform'] == 'discord'
        assert result['community_id'] == 123456
        assert result['source_id'] == 'mee6_test'
        assert result['stats']['total_processed'] == 100

    def test_get_migration_status_existing(self, rank_db):
        """Test getting migration status that exists."""
        stats = {
            'source_type': 'mee6',
            'total_processed': 100,
            'date': '2026-01-01T00:00:00+00:00',
        }

        rank_db.set_migration_completed(
            platform='discord',
            community_id=123456,
            source_id='mee6_test',
            stats=stats,
        )

        status = rank_db.get_migration_status(
            platform='discord',
            community_id=123456,
            source_id='mee6_test',
        )

        assert status is not None
        assert status['platform'] == 'discord'
        assert status['stats']['total_processed'] == 100

    def test_multiple_migrations(self, rank_db):
        """Test storing multiple migration records."""
        # Set multiple migrations
        for i in range(3):
            stats = {
                'source_type': 'mee6',
                'total_processed': i * 10,
                'date': f'2026-01-0{i+1}T00:00:00+00:00',
            }

            rank_db.set_migration_completed(
                platform='discord',
                community_id=123456 + i,
                source_id=f'source_{i}',
                stats=stats,
            )

        # Verify each migration can be retrieved
        for i in range(3):
            status = rank_db.get_migration_status(
                platform='discord',
                community_id=123456 + i,
                source_id=f'source_{i}',
            )
            assert status is not None
            assert status['stats']['total_processed'] == i * 10

    def test_same_user_different_communities(self, rank_db):
        """Test that same user ID in different communities are tracked separately."""
        # Create same user ID in two communities
        rank_db.update_user_data(
            platform='discord',
            community_id=111,
            user_id=999,
            data={'user_id': 999, 'community_id': 111, 'xp': 100},
        )
        rank_db.update_user_data(
            platform='discord',
            community_id=222,
            user_id=999,
            data={'user_id': 999, 'community_id': 222, 'xp': 200},
        )

        # Retrieve from each community
        user_in_111 = rank_db.get_user_data(
            platform='discord',
            community_id=111,
            user_id=999,
        )
        user_in_222 = rank_db.get_user_data(
            platform='discord',
            community_id=222,
            user_id=999,
        )

        assert user_in_111['xp'] == 100
        assert user_in_222['xp'] == 200
