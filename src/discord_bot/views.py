# standard imports
from typing import Tuple

# lib imports
import discord
from discord.ui.select import Select
from discord.ui.button import Button

# local imports
from src.common.common import avatar, bot_name, colors
from src.discord_bot.helpers import get_json
from src.discord_bot.modals import RefundModal


class DocsCommandDefaultProjects:
    """
    Class representing default projects for ``docs`` slash command.

    Attributes
    ----------
    self.projects : Union[dict, list]
        The json representation of our readthedocs projects.
    self.project_options : list
        A list of `discord.SelectOption` objects.
    """
    def __init__(self):
        self.projects = get_json(url='https://app.lizardbyte.dev/dashboard/readthedocs/projects.json')
        self.projects_options = []
        # Track used values to prevent duplicates
        used_values = set()
        self.value_to_project_map = {}

        counter = 0
        for project in self.projects:
            try:
                parent_project = project['subproject_of']['name']
            except (KeyError, TypeError):
                parent_project = None

            # Extract repository name to use as value
            original_value = project['repository']['url'].rsplit('/', 1)[-1].rsplit('.git', 1)[0]
            value = original_value

            # make sure the value is unique
            value = f"{original_value}-{counter}"

            # Add to used values set
            used_values.add(value)

            # Store mapping of modified value to original project identifier
            self.value_to_project_map[value] = original_value

            self.projects_options.append(
                discord.SelectOption(
                    label=project['name'],
                    value=value,
                    description=f"Subproject of {parent_project}" if parent_project else None
                )
            )

            counter += 1


class DocsCommandView(discord.ui.View):
    """
    Class representing `discord.ui.View` for ``docs`` slash command.

    Attributes
    ----------
    self.ctx : discord.ApplicationContext
        Request message context.
    self.docs_project : str
        The project name.
    self.docs_version : str
        The url to the documentation of the selected version.
    """
    def __init__(self, ctx: discord.ApplicationContext):
        super().__init__(timeout=45)

        self.ctx = ctx
        self.interaction = None

        # final values
        self.docs_project = None
        self.docs_version = None

        # Create projects and store the mapping
        projects_handler = DocsCommandDefaultProjects()
        self.project_value_map = projects_handler.value_to_project_map

        # reset the first select menu because it remembers the last selected value
        self.children[0].options = projects_handler.projects_options

    # check selections completed
    def check_completion_status(self) -> Tuple[bool, discord.Embed]:
        """
        Check if Select Menu choices are valid.

        Obtaining a valid docs url depends on the selections made in the select menus. This function checks if
        the conditions are met to provide a valid docs url.

        Returns
        -------
        Tuple[bool, discord.Embed]
        """
        complete = False
        embed = discord.Embed()
        embed.set_footer(text=bot_name, icon_url=avatar)

        url = self.docs_version

        if self.docs_project and self.docs_version:  # the project and version are selected
            complete = True

        if complete:
            embed.title = self.docs_project
            embed.description = f'The selected docs are available at {url}'
            embed.color = colors['green']
            embed.url = url
        else:
            # info is not complete
            embed.title = "Select the remaining values"
            embed.description = None
            embed.color = colors['orange']
            embed.url = None

        return complete, embed

    async def on_timeout(self):
        """
        Timeout callback.

        Disable children items, and edit the original message.
        """
        for child in self.children:
            child.disabled = True

        complete, embed = self.check_completion_status()

        if not complete:
            embed.title = "Command timed out..."
            embed.color = colors['red']
            delete_after = 30  # delete after 30 seconds
        else:
            delete_after = None  # do not delete

        await self.ctx.interaction.edit_original_message(embed=embed, view=self, delete_after=delete_after)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        Check the interaction.

        Ensure the user interacting with the interaction is the user that initiated it.

        Parameters
        ----------
        interaction : discord.Interaction

        Returns
        -------
        bool
            If interaction user is the author or bot owner return ``True``, otherwise ``False``.
        """
        if interaction.user and interaction.user.id in (self.ctx.bot.owner_id, self.ctx.author.id):
            return True
        else:
            await interaction.response.send_message('This pagination menu cannot be controlled by you, sorry!',
                                                    ephemeral=True)
            return False

    async def callback(self, select: Select, interaction: discord.Interaction):
        """
        Callback for select menus of `docs` command.

        Updates Select Menus depending on currently selected values. Updates embed message when requirements are met.

        Parameters
        ----------
        select : discord.ui.select.Select
            The `Select` object interacted with.
        interaction : discord.Interaction
            The original discord interaction object.
        """
        self.interaction = interaction

        select_index = None
        index = 0
        for child in self.children:
            if child == select:
                select_index = index  # this is the current child... user interacted with this child

            # disable dependent drop downs
            if select_index is not None:
                if index - select_index - 1 <= 0:  # add 1 to select index to always allow subtracting
                    child.disabled = False
                else:
                    child.disabled = True
                    child.options = [discord.SelectOption(label='error')]

                if index - select_index == 1:  # this is the next child
                    child.options = [discord.SelectOption(label='0')]

                    if child == self.children[1]:  # choose docs version
                        selected_value = self.children[0].values[0]

                        # Get the original project identifier from the mapping
                        readthedocs = self.project_value_map.get(selected_value, selected_value)

                        versions = get_json(
                            url=f'https://app.lizardbyte.dev/dashboard/readthedocs/versions/{readthedocs}.json')

                        options = []
                        for version in versions:
                            if version['active'] and version['built']:
                                options.append(discord.SelectOption(
                                    label=version['slug'],
                                    value=version['urls']['documentation'],
                                    description=f"Docs for {version['slug']} {version['type']}"
                                ))

                        child.options = options[:25]  # limit to 25 options

            index += 1

        # set the currently selected value to the default item
        for option in select.options:
            if option.value == select.values[0]:
                option.default = True
            else:
                option.default = False

        # reset values
        try:
            self.docs_project = self.children[0].values[0]
            if self.children[1].values:
                self.docs_version = self.children[1].values[0]
            else:
                self.docs_version = None
        except IndexError:
            pass
        if select == self.children[0]:  # chose the docs project
            self.docs_version = None

        _, embed = self.check_completion_status()

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.select(
        placeholder="Choose docs...",
        disabled=False,
        min_values=1,
        max_values=1,
        options=DocsCommandDefaultProjects().projects_options
    )
    async def slug_callback(self, select: Select, interaction: discord.Interaction):
        await self.callback(select=select, interaction=interaction)

    @discord.ui.select(
        placeholder="Choose version...",
        disabled=True,
        min_values=1,
        max_values=1,
        options=[discord.SelectOption(label='error')]
    )
    async def version_callback(self, select: Select, interaction: discord.Interaction):
        await self.callback(select=select, interaction=interaction)


class DonateCommandView(discord.ui.View):
    """
    Class representing `discord.ui.View` for ``donate`` slash command.

    Attributes
    ----------
    self.donation_methods : dict
        Dictionary containing donation methods, names, and urls.
    """
    def __init__(self):
        super().__init__(timeout=None)  # timeout of the view must be set to None, view is persistent

        self.donation_methods = {
            'github': {
                'name': 'GitHub',
                'url': 'https://github.com/sponsors/LizardByte',
            },
            'patreon': {
                'name': 'Patreon',
                'url': 'https://www.patreon.com/LizardByte',
            },
            'paypal': {
                'name': 'PayPal',
                'url': 'https://paypal.me/ReenigneArcher',
            },
        }

        for method in self.donation_methods:
            button = discord.ui.Button(
                label=self.donation_methods[method]['name'],
                url=self.donation_methods[method]['url'],
                style=discord.ButtonStyle.link,
            )

            self.add_item(button)


class RefundCommandView(discord.ui.View):
    """
    Class representing `discord.ui.View` for ``refund`` slash command.
    """
    def __init__(self):
        super().__init__(timeout=None)  # timeout of the view must be set to None, view is persistent

    @discord.ui.button(label="Refund form", style=discord.ButtonStyle.red, custom_id='button-refund')
    async def button_callback(self, button: Button, interaction: discord.Interaction):
        await interaction.response.send_modal(RefundModal(title="Refund Request Form"))
