# standard imports
import datetime
import os

# lib imports
import discord
from discord.commands import Option
from discord.ext import tasks
import git
import mistletoe
from mistletoe.markdown_renderer import MarkdownRenderer

# local imports
from src.common.common import avatar, bot_name, colors, data_dir
from src.discord_bot.views import DocsCommandView
from src.discord_bot import cogs_common


class SupportCommandsCog(discord.Cog):
    def __init__(self, bot):
        self.bot: discord.Bot = bot

        self.commands = {}
        self.commands_for_removal = []

        self.repo_url = os.getenv("SUPPORT_COMMANDS_REPO", "https://github.com/LizardByte/support-bot-commands")
        self.repo_branch = os.getenv("SUPPORT_COMMANDS_BRANCH", "master")
        self.local_dir = os.path.join(data_dir, "support-bot-commands")
        self.commands_dir = os.path.join(self.local_dir, "docs")
        self.relative_commands_dir = os.path.relpath(self.commands_dir, self.local_dir)

    @discord.Cog.listener()
    async def on_ready(self):
        # Clone/update the repository
        self.update_repo()

        # Create commands
        self.create_commands()

        # Start the self update task
        self.self_update.start()

    @tasks.loop(minutes=15.0)
    async def self_update(self):
        self.update_repo()
        self.create_commands()
        await self.bot.sync_commands()

    def update_repo(self):
        # Clone or pull the repository
        if not os.path.exists(self.local_dir):
            repo = git.Repo.clone_from(self.repo_url, self.local_dir)
        else:
            repo = git.Repo(self.local_dir)
            origin = repo.remotes.origin

            # Fetch the latest changes from the upstream
            origin.fetch()

            # Reset the local branch to match the upstream
            repo.git.reset('--hard', f'origin/{self.repo_branch}')

            for f in repo.untracked_files:
                # remove untracked files
                os.remove(os.path.join(self.local_dir, f))

        # Checkout the branch
        repo.git.checkout(self.repo_branch)

    def get_project_commands(self):
        projects = []
        for project in os.listdir(self.commands_dir):
            project_dir = os.path.join(self.commands_dir, project)
            if os.path.isdir(project_dir):
                projects.append(project)
        return projects

    def create_commands(self):
        for project in self.get_project_commands():
            project_dir = os.path.join(self.commands_dir, project)
            if os.path.isdir(project_dir):
                self.create_project_commands(project=project, project_dir=project_dir)

    def create_project_commands(self, project, project_dir):
        # Get the list of commands in the project directory
        command_choices = []
        for cmd in os.listdir(project_dir):
            cmd_path = os.path.join(project_dir, cmd)
            if os.path.isfile(cmd_path) and cmd.endswith('.md'):
                cmd_name = os.path.splitext(cmd)[0]
                command_choices.append(discord.OptionChoice(name=cmd_name, value=cmd_name))

        # Check if a command with the same name already exists
        if project in self.commands:
            # Update the command options
            project_command = self.commands[project]
            project_command.options = [
                Option(
                    name='command',
                    description='The command to run',
                    type=discord.SlashCommandOptionType.string,
                    choices=command_choices,
                    required=True,
                )
            ]
        else:
            # Create a slash command for the project
            @self.bot.slash_command(name=project, description=f"Commands for the {project} project.",
                                    options=[
                                        Option(
                                            name='command',
                                            description='The command to run',
                                            type=discord.SlashCommandOptionType.string,
                                            choices=command_choices,
                                            required=True,
                                        )
                                    ])
            async def project_command(ctx: discord.ApplicationContext, command: str):
                # Determine the command file path
                command_file = os.path.join(project_dir, f"{command}.md")

                # Read the command file
                with open(command_file, "r", encoding='utf-8') as file:
                    with MarkdownRenderer(
                            max_line_length=4096,  # this must be set to reflow the text
                            normalize_whitespace=True) as renderer:
                        description = renderer.render(mistletoe.Document(file))

                source_url = (f"{self.repo_url}/blob/{self.repo_branch}/{self.relative_commands_dir}/"
                              f"{project}/{command}.md")

                embed = discord.Embed(
                    color=colors['yellow'],
                    description=description,
                    timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
                    title="See on GitHub",
                    url=source_url,
                )
                embed.set_footer(text=f"Requested by {ctx.author.display_name}")
                await ctx.respond(embed=embed, ephemeral=False)

        self.commands[project] = project_command

    @discord.slash_command(
        name="docs",
        description="Get docs for any project."
    )
    async def docs_command(
            self,
            ctx: discord.ApplicationContext,
            user: Option(
                discord.Member,
                description=cogs_common.user_mention_desc,
                required=False,
            ),
    ):
        """
        Sends a discord embed, with `Select Menus` allowing the user to select the specific documentation,
        to the server and channel where the command was issued.

        Parameters
        ----------
        ctx : discord.ApplicationContext
            Request message context.
        user : discord.Member
            Username to mention in response.
        """
        embed = discord.Embed(title="Select a project", color=colors['yellow'])
        embed.set_footer(text=bot_name, icon_url=avatar)

        if user:
            await ctx.respond(
                f'{ctx.author.mention}, {user.mention}',
                embed=embed,
                ephemeral=False,
                view=DocsCommandView(ctx=ctx)
            )
        else:
            await ctx.respond(
                f'{ctx.author.mention}',
                embed=embed,
                ephemeral=False,
                view=DocsCommandView(ctx=ctx)
            )


def setup(bot: discord.Bot):
    bot.add_cog(SupportCommandsCog(bot=bot))
