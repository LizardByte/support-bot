# lib imports
from praw import models


class RedditRankManager:
    """
    Class to handle Reddit rank-related functionality.
    """

    def __init__(self, bot):
        """
        Initialize the Reddit rank manager.

        Parameters
        ----------
        bot : Bot
            Reddit bot instance
        """
        self.bot = bot
        self.rank_system = bot.rank_system
        self.subreddit_id = bot.subreddit.id if bot.subreddit else None

    def get_user_rank(self, username: str):
        """
        Get rank information for a specific Reddit user.

        Parameters
        ----------
        username : str
            Reddit username to look up

        Returns
        -------
        dict
            Rank information including level, XP, and position
        """
        try:
            # Create a dummy user object for the rank system
            class DummyRedditUser:
                def __init__(self, name, subreddit_id):
                    self.name = name
                    self.id = name  # Use the username as ID
                    self.subreddit_id = subreddit_id

            dummy_user = DummyRedditUser(username, self.subreddit_id)

            # Get user data from rank system
            user_data = self.rank_system.get_rank_data(
                platform='reddit',
                user=dummy_user,
                create_if_not_exists=False,
            )
            level = self.rank_system.calculate_level(xp=user_data['xp'])
            rank_position = self.rank_system.get_user_rank_position(
                platform='reddit',
                user=dummy_user,
            )

            # Calculate progress to next level
            current_level_xp = self.rank_system.calculate_xp_for_level(level)
            next_level_xp = self.rank_system.calculate_xp_for_level(level + 1)
            progress = (user_data['xp'] - current_level_xp) / (next_level_xp - current_level_xp) \
                if next_level_xp > current_level_xp else 0

            return {
                'username': username,
                'level': level,
                'xp': user_data['xp'],
                'message_count': user_data.get('message_count', 0),
                'submission_count': user_data.get('submission_count', 0),
                'comment_count': user_data.get('comment_count', 0),
                'rank': rank_position,
                'progress': progress,
                'xp_for_next_level': next_level_xp - user_data['xp']
            }
        except Exception as e:
            print(f"Error getting rank for Reddit user {username}: {e}")
            return None

    def get_leaderboard(self, limit: int = 10, offset: int = 0):
        """
        Get the Reddit leaderboard.

        Parameters
        ----------
        limit : int
            Maximum number of entries to return
        offset : int
            Number of entries to skip

        Returns
        -------
        list
            List of user rank data
        """
        try:
            leaderboard = self.rank_system.get_leaderboard(
                platform='reddit',
                community_id=self.subreddit_id,
                limit=limit,
                offset=offset
            )

            # Add level to each entry
            for entry in leaderboard:
                entry['level'] = self.rank_system.calculate_level(entry['xp'])

            return leaderboard
        except Exception as e:
            print(f"Error getting Reddit leaderboard: {e}")
            return []

    def respond_to_rank_command(self, comment: models.Comment):
        """
        Respond to a /rank command in Reddit.

        Parameters
        ----------
        comment : models.Comment
            The Reddit comment containing the rank command

        Returns
        -------
        bool
            True if the command was handled, False otherwise
        """
        try:
            # Parse command - format could be "/rank" or "/rank username"
            parts = comment.body.strip().split()

            if len(parts) == 1 and parts[0].lower() == "/rank":
                # User is checking their own rank
                username = comment.author.name
            elif len(parts) == 2 and parts[0].lower() == "/rank":
                # User is checking someone else's rank
                username = parts[1].strip()
                # Remove u/ prefix if present
                if username.startswith('u/'):
                    username = username[2:]
            else:
                # Not a valid rank command
                return False

            # Get rank data
            rank_data = self.get_user_rank(username)

            if not rank_data:
                comment.reply(f"Sorry, I couldn't find rank data for u/{username}.")
                return True

            # Create a nice Reddit markdown response
            level_bar = "▰" * int(rank_data['progress'] * 20) + "▱" * (20 - int(rank_data['progress'] * 20))

            response = (
                f"# Rank for u/{rank_data['username']}\n\n"
                f"**Rank:** #{rank_data['rank']}\n\n"
                f"**Level:** {rank_data['level']}\n\n"
                f"**XP:** {rank_data['xp']:,}\n\n"
                f"**Progress to Level {rank_data['level'] + 1}:** {int(rank_data['progress'] * 100)}%\n\n"
                f"{level_bar}\n\n"
                f"*Need {rank_data['xp_for_next_level']:,} more XP for next level*\n\n"
                f"**Activity:** {rank_data['message_count']:,} total posts "
                f"({rank_data.get('submission_count', 0):,} submissions, "
                f"{rank_data.get('comment_count', 0):,} comments)\n\n"
                f"---\n^(This action was performed by a bot. For issues, please contact the moderators.)"
            )

            comment.reply(response)
            return True

        except Exception as e:
            print(f"Error responding to rank command: {e}")
            return False

    def respond_to_leaderboard_command(self, comment: models.Comment):
        """
        Respond to a /leaderboard command in Reddit.

        Parameters
        ----------
        comment : models.Comment
            The Reddit comment containing the leaderboard command

        Returns
        -------
        bool
            True if the command was handled, False otherwise
        """
        try:
            # Parse command - format could be "/leaderboard" or "/leaderboard 2" for page
            parts = comment.body.strip().split()

            if len(parts) == 1 and parts[0].lower() == "/leaderboard":
                # Default to first page
                page = 1
            elif len(parts) == 2 and parts[0].lower() == "/leaderboard":
                # User specified a page
                try:
                    page = int(parts[1])
                    if page < 1:
                        page = 1
                except ValueError:
                    page = 1
            else:
                # Not a valid leaderboard command
                return False

            per_page = 10
            offset = (page - 1) * per_page

            # Get leaderboard data
            leaderboard_data = self.get_leaderboard(limit=per_page, offset=offset)

            if not leaderboard_data:
                comment.reply("No leaderboard data available yet.")
                return True

            # Create a nice Reddit markdown response
            response = f"# r/{self.bot.subreddit_name} XP Leaderboard (Page {page})\n\n"
            response += "Rank | User | Level | XP | Activity\n"
            response += "---|---|---|---|---\n"

            for i, entry in enumerate(leaderboard_data, start=1):
                username = entry.get('username', f"User {entry['user_id']}")
                response += f"{offset + i} | u/{username} | {entry['level']} | {entry['xp']:,} | "
                response += f"{entry.get('message_count', 0):,} posts\n"

            response += "\n\n---\n^(This action was performed by a bot. For issues, please contact the moderators.)"

            comment.reply(response)
            return True

        except Exception as e:
            print(f"Error responding to leaderboard command: {e}")
            return False
