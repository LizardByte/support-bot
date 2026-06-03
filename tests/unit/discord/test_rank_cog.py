# standard imports
import math
from types import SimpleNamespace

# lib imports
import pytest

# local imports
from src.common import globals
from src.discord_bot.cogs.rank import RankCog


def rank_cog(mocker):
    cog = RankCog.__new__(RankCog)
    cog.bot = SimpleNamespace(fetch_user=mocker.AsyncMock())
    cog.rank_system = SimpleNamespace(
        calculate_level=lambda xp: xp // 100,
        calculate_xp_for_level=lambda level: level * 100,
    )
    return cog


@pytest.mark.asyncio
async def test_build_leaderboard_embed_discord(mocker):
    cog = rank_cog(mocker)
    cog.bot.fetch_user.side_effect = [
        SimpleNamespace(display_name='Display User'),
        None,
    ]
    ctx = SimpleNamespace(guild=SimpleNamespace(icon=SimpleNamespace(url='https://example.com/icon.png')))
    leaderboard_data = [
        {'user_id': 1, 'username': 'first', 'xp': 150, 'message_count': 7},
        {'user_id': 2, 'username': 'second', 'xp': 250},
    ]

    embed = await cog.build_leaderboard_embed(
        platform='discord',
        leaderboard_data=leaderboard_data,
        page=2,
        total_pages=3,
        total_users=20,
        ctx=ctx,
    )

    assert embed.title == '🏆 Discord XP Leaderboard'
    assert '**Display User**' in embed.description
    assert 'second' in embed.description
    assert '┄┄┄┄┄┄┄┄┄┄┄┄' in embed.description
    assert 'Page 2/3 • 20 total ranked users' in embed.footer.text
    assert embed.thumbnail.url == 'https://example.com/icon.png'


@pytest.mark.asyncio
async def test_build_leaderboard_embed_reddit(mocker):
    cog = rank_cog(mocker)
    original_reddit_bot = globals.REDDIT_BOT
    globals.REDDIT_BOT = SimpleNamespace(
        subreddit=SimpleNamespace(community_icon='https://example.com/reddit.png'),
    )

    try:
        embed = await cog.build_leaderboard_embed(
            platform='reddit',
            leaderboard_data=[{'user_id': 'abc', 'username': 'reddit_user', 'xp': 0}],
            page=1,
            total_pages=1,
            total_users=1,
            ctx=SimpleNamespace(guild=SimpleNamespace(icon=None)),
        )
    finally:
        globals.REDDIT_BOT = original_reddit_bot

    assert embed.title == '🏆 Reddit XP Leaderboard'
    assert '**u/reddit_user**' in embed.description
    assert embed.thumbnail.url == 'https://example.com/reddit.png'


@pytest.mark.asyncio
async def test_leaderboard_username_exception(mocker):
    cog = rank_cog(mocker)
    cog.bot.fetch_user.side_effect = Exception('discord unavailable')

    username = await cog._leaderboard_username(
        platform='discord',
        entry={'user_id': 123, 'username': 'fallback'},
    )

    assert username == '**fallback**'


def test_leaderboard_format_helpers(mocker):
    cog = rank_cog(mocker)

    assert cog._leaderboard_rank_display(rank_num=1) == '🥇'
    assert cog._leaderboard_rank_display(rank_num=11) == '`#11`'
    assert cog._leaderboard_progress_percent(xp=100, current_level_xp=100, next_level_xp=100) == 0
    assert math.isclose(
        cog._leaderboard_progress_percent(xp=150, current_level_xp=100, next_level_xp=200),
        0.5,
    )
    assert cog._progress_bar(progress=0.25, progress_bar_length=4) == '▰▱▱▱'
    level, progress, progress_bar = cog._leaderboard_progress(entry={'xp': 150})
    assert level == 1
    assert math.isclose(progress, 0.5)
    assert progress_bar == '▰▰▰▰▰▱▱▱▱▱'
