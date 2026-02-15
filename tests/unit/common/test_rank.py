# standard imports
import os
import tempfile
import time
from unittest.mock import MagicMock, patch

# lib imports
import pytest

# local imports
from src.common.rank import RankSystem


class MockDiscordUser:
    """Mock Discord user for testing."""
    def __init__(self, user_id: int, name: str = "TestUser", guild_id: int = 123456789):
        self.id = user_id
        self.name = name
        self.display_name = name
        self.guild = MagicMock()
        self.guild.id = guild_id


class MockRedditUser:
    """Mock Reddit user for testing."""
    def __init__(self, user_id: str, name: str = "TestUser", subreddit_id: str = "test_subreddit"):
        self.id = user_id
        self.name = name
        self.subreddit_id = subreddit_id


class MockBot:
    """Mock bot for testing."""
    def __init__(self):
        self.user = MagicMock()
        self.user.id = 999999999


class TestRankSystem:
    @pytest.fixture
    def temp_db_dir(self):
        """Create a temporary directory for test databases."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot instance."""
        return MockBot()

    @pytest.fixture
    def rank_system(self, temp_db_dir, mock_bot):
        """Create a RankSystem instance with temporary database."""
        # Set environment variables for git-free operation
        with patch.dict(os.environ, {}, clear=False):
            # Remove git-related env vars if they exist
            env_patch = {k: v for k, v in os.environ.items()
                        if k not in ['GIT_TOKEN', 'GITHUB_TOKEN', 'GIT_USER_NAME', 'GIT_USER_EMAIL']}
            with patch.dict(os.environ, env_patch, clear=True):
                # Patch RankDatabase to use temp_db_dir
                with patch('src.common.rank.RankDatabase') as mock_rank_db:
                    from src.common.rank_database import RankDatabase
                    mock_rank_db.return_value = RankDatabase(db_dir=temp_db_dir, use_git=False)

                    system = RankSystem(
                        bot=mock_bot,
                        xp_range=(10, 20),
                        cooldown=5,
                    )
                    yield system

    def test_init(self, rank_system, mock_bot):
        """Test RankSystem initialization."""
        assert rank_system.bot == mock_bot
        assert rank_system.xp_range == (10, 20)
        assert rank_system.cooldown == 5
        assert rank_system.last_activity == {}

    def test_calculate_level(self, rank_system):
        """Test level calculation from XP."""
        # Test various XP values
        assert rank_system.calculate_level(xp=0) == 0
        assert rank_system.calculate_level(xp=100) == 1
        assert rank_system.calculate_level(xp=355) == 2
        assert rank_system.calculate_level(xp=1000) == 4
        assert rank_system.calculate_level(xp=10000) == 13

    def test_calculate_xp_for_level(self, rank_system):
        """Test XP calculation for specific level."""
        # Test various levels
        assert rank_system.calculate_xp_for_level(level=0) == 0
        assert rank_system.calculate_xp_for_level(level=1) == 100
        assert rank_system.calculate_xp_for_level(level=2) == 355
        assert rank_system.calculate_xp_for_level(level=5) == 2345

    def test_get_community_id_discord(self, rank_system):
        """Test getting community ID for Discord user."""
        user = MockDiscordUser(user_id=12345, guild_id=987654)
        community_id = rank_system.get_community_id(platform='discord', user=user)
        assert community_id == 987654

    def test_get_community_id_reddit(self, rank_system):
        """Test getting community ID for Reddit user."""
        user = MockRedditUser(user_id='test123', subreddit_id='lizardbyte')
        community_id = rank_system.get_community_id(platform='reddit', user=user)
        assert community_id == 'lizardbyte'

    def test_get_rank_data_new_user(self, rank_system):
        """Test getting rank data for a new user."""
        user = MockDiscordUser(user_id=12345)
        data = rank_system.get_rank_data(
            platform='discord',
            user=user,
            create_if_not_exists=True,
        )

        assert data is not None
        assert data['user_id'] == 12345
        assert data['community_id'] == 123456789
        assert data['xp'] == 0
        assert data['message_count'] == 0

    def test_get_rank_data_existing_user(self, rank_system):
        """Test getting rank data for an existing user."""
        user = MockDiscordUser(user_id=12345)

        # Create user first
        rank_system.get_rank_data(
            platform='discord',
            user=user,
            create_if_not_exists=True,
        )

        # Retrieve again
        data = rank_system.get_rank_data(
            platform='discord',
            user=user,
            create_if_not_exists=False,
        )

        assert data is not None
        assert data['user_id'] == 12345

    def test_update_rank_data(self, rank_system):
        """Test updating rank data."""
        user = MockDiscordUser(user_id=12345)

        # Create user
        initial_data = rank_system.get_rank_data(
            platform='discord',
            user=user,
            create_if_not_exists=True,
        )

        # Update data
        initial_data['xp'] = 500
        initial_data['message_count'] = 10

        updated_data = rank_system.update_rank_data(
            platform='discord',
            user=user,
            data=initial_data,
        )

        assert updated_data['xp'] == 500
        assert updated_data['message_count'] == 10

    def test_award_xp_new_user(self, rank_system):
        """Test awarding XP to a new user."""
        user = MockDiscordUser(user_id=12345)

        result = rank_system.award_xp(platform='discord', user=user)

        assert result is not None
        assert 'user_data' in result
        assert 'xp_gain' in result
        assert 'level' in result
        assert 'level_up' in result
        assert 10 <= result['xp_gain'] <= 20  # Within xp_range
        assert result['user_data']['xp'] == result['xp_gain']
        assert result['user_data']['message_count'] == 1
        assert result['level'] >= 0

    def test_award_xp_cooldown(self, rank_system):
        """Test that XP award respects cooldown."""
        user = MockDiscordUser(user_id=12345)

        # First award should succeed
        result1 = rank_system.award_xp(platform='discord', user=user)
        assert result1 is not None

        # Immediate second award should be on cooldown
        result2 = rank_system.award_xp(platform='discord', user=user)
        assert result2 is None

        # After cooldown, should succeed
        time.sleep(6)  # Wait for cooldown (5 seconds + buffer)
        result3 = rank_system.award_xp(platform='discord', user=user)
        assert result3 is not None

    def test_award_xp_level_up(self, rank_system):
        """Test level up detection when awarding XP."""
        user = MockDiscordUser(user_id=12345)

        # Create user with XP close to level up (level 0 -> 1 requires 100 XP)
        initial_data = rank_system.get_rank_data(
            platform='discord',
            user=user,
            create_if_not_exists=True,
        )
        initial_data['xp'] = 90
        rank_system.update_rank_data(platform='discord', user=user, data=initial_data)

        # Award XP should trigger level up
        time.sleep(6)  # Ensure no cooldown
        result = rank_system.award_xp(platform='discord', user=user)

        assert result is not None
        assert result['level_up'] is True
        assert result['level'] == 1
        assert result['old_level'] == 0

    def test_get_leaderboard(self, rank_system):
        """Test getting leaderboard."""
        # Create multiple users with different XP
        users = [
            MockDiscordUser(user_id=1, name="User1"),
            MockDiscordUser(user_id=2, name="User2"),
            MockDiscordUser(user_id=3, name="User3"),
        ]

        xp_values = [500, 1000, 250]

        for user, xp in zip(users, xp_values):
            data = rank_system.get_rank_data(
                platform='discord',
                user=user,
                create_if_not_exists=True,
            )
            data['xp'] = xp
            data['username'] = user.name
            rank_system.update_rank_data(platform='discord', user=user, data=data)

        # Get leaderboard
        leaderboard = rank_system.get_leaderboard(
            platform='discord',
            user=users[0],  # Use first user to get guild_id
            limit=10,
        )

        assert len(leaderboard) == 3
        # Should be sorted by XP descending
        assert leaderboard[0]['xp'] == 1000  # User2
        assert leaderboard[1]['xp'] == 500   # User1
        assert leaderboard[2]['xp'] == 250   # User3

    def test_get_leaderboard_pagination(self, rank_system):
        """Test leaderboard pagination."""
        # Create 5 users
        users = [MockDiscordUser(user_id=i, name=f"User{i}") for i in range(5)]

        for i, user in enumerate(users):
            data = rank_system.get_rank_data(
                platform='discord',
                user=user,
                create_if_not_exists=True,
            )
            data['xp'] = (i + 1) * 100
            rank_system.update_rank_data(platform='discord', user=user, data=data)

        # Get first page (limit 2)
        page1 = rank_system.get_leaderboard(
            platform='discord',
            user=users[0],
            limit=2,
            offset=0,
        )

        assert len(page1) == 2
        assert page1[0]['xp'] == 500  # Highest

        # Get second page
        page2 = rank_system.get_leaderboard(
            platform='discord',
            user=users[0],
            limit=2,
            offset=2,
        )

        assert len(page2) == 2
        assert page2[0]['xp'] == 300

    def test_reddit_platform(self, rank_system):
        """Test rank system with Reddit platform."""
        user = MockRedditUser(user_id='reddit123', name='RedditUser')

        result = rank_system.award_xp(platform='reddit', user=user)

        assert result is not None
        assert result['user_data']['user_id'] == 'reddit123'
        assert result['user_data']['community_id'] == 'test_subreddit'

    def test_get_migration_status_none(self, rank_system):
        """Test getting migration status when none exists."""
        status = rank_system.get_migration_status(
            platform='discord',
            community_id=123456,
            source_id='mee6',
        )
        assert status is None

    def test_set_migration_completed(self, rank_system):
        """Test marking migration as completed."""
        stats = {
            'source_type': 'mee6',
            'total_processed': 100,
            'date': '2026-01-01T00:00:00+00:00',
        }

        result = rank_system.set_migration_completed(
            platform='discord',
            community_id=123456,
            source_id='mee6_test',
            stats=stats,
        )

        assert result is not None
        assert result['platform'] == 'discord'
        assert result['stats']['total_processed'] == 100

        # Verify we can retrieve it
        status = rank_system.get_migration_status(
            platform='discord',
            community_id=123456,
            source_id='mee6_test',
        )

        assert status is not None
        assert status['stats']['total_processed'] == 100

    def test_multiple_communities(self, rank_system):
        """Test that users in different communities are tracked separately."""
        user1 = MockDiscordUser(user_id=12345, guild_id=111)
        user2 = MockDiscordUser(user_id=12345, guild_id=222)

        # Award XP to same user ID in different communities
        result1 = rank_system.award_xp(platform='discord', user=user1)
        time.sleep(6)  # Wait for cooldown
        result2 = rank_system.award_xp(platform='discord', user=user2)

        assert result1 is not None
        assert result2 is not None

        # Should have different data
        data1 = rank_system.get_rank_data(platform='discord', user=user1)
        data2 = rank_system.get_rank_data(platform='discord', user=user2)

        assert data1['community_id'] != data2['community_id']
