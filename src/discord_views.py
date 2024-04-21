# standard imports
from typing import Tuple

# lib imports
from bs4 import BeautifulSoup
import discord
from discord.ui.select import Select
from discord.ui.button import Button
import requests

# local imports
from discord_avatar import avatar
from discord_constants import bot_name
from discord_helpers import get_json
from discord_modals import RefundModal


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
        self.projects = get_json(url='https://app.lizardbyte.dev/uno/readthedocs/projects.json')
        self.projects_options = []
        for project in self.projects:
            try:
                parent_project = project['subproject_of']['name']
            except (KeyError, TypeError):
                parent_project = None

            self.projects_options.append(
                discord.SelectOption(label=project['name'],
                                     value=project['repository']['url'].rsplit('/', 1)[-1].rsplit('.git', 1)[0],
                                     description=f"Subproject of {parent_project}" if parent_project else None)
            )


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
    self.docs_category : str
        The name of the selected category.
    self.docs_page : str
        The name of the selected page.
    self.docs_section : str
        The name of the selected section.
    self.html : bytes
        Content of `requests.get()` in bytes.
    self.soup : bs4.BeautifulSoup
        BeautifulSoup object of `self.html`
    self.toc : ResultSet
        Docs table of contents.
    self.categories : list
        A list of Docs categories.
    self.pages : list
        A list of pages for the selected category.
    self.sections : list
        A list of sections for the selected page.
    """
    def __init__(self, ctx: discord.ApplicationContext):
        super().__init__(timeout=45)

        self.ctx = ctx
        self.interaction = None

        # final values
        self.docs_project = None
        self.docs_version = None
        self.docs_category = None
        self.docs_page = None
        self.docs_section = None

        # intermediate values
        self.html = None
        self.soup = None
        self.toc = None
        self.categories = None
        self.pages = None
        self.sections = None

        # reset the first select menu because it remembers the last selected value
        self.children[0].options = DocsCommandDefaultProjects().projects_options

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

        url = f'{self.docs_version}{self.docs_section}'

        if self.docs_project and self.docs_version:  # the project and version are selected
            if self.docs_category is not None:  # category has a value, which may be ""
                if self.docs_category:  # category is selected, so the next item must not be blank
                    if self.docs_page is not None and self.docs_section is not None:  # info is complete
                        complete = True
                else:  # info is complete IF category is ""
                    complete = True

        if complete:
            embed.title = f'{self.docs_project} | {self.docs_category}' if self.docs_category else self.docs_project
            embed.description = f'The selected docs are available at {url}'
            embed.color = 0x39FF14  # PyCharm complains that the color is read only, but this works anyway
            embed.url = url
        else:
            # info is not complete
            embed.title = "Select the remaining values"
            embed.description = None
            embed.color = 0xF1C232
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
            embed.color = 0xDC143C
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
                        readthedocs = self.children[0].values[0]

                        versions = get_json(
                            url=f'https://app.lizardbyte.dev/uno/readthedocs/versions/{readthedocs}.json')

                        options = []
                        for version in versions:
                            if version['active'] and version['built']:
                                options.append(discord.SelectOption(
                                    label=version['slug'],
                                    value=version['urls']['documentation'],
                                    description=f"Docs for {version['slug']} {version['type']}"
                                ))

                        child.options = options

                    if child == self.children[2]:  # choose the docs category
                        url = self.children[1].values[0]

                        self.html = requests.get(url=url).content
                        self.soup = BeautifulSoup(self.html, 'html.parser')

                        self.toc = self.soup.select("div[class*=toctree-wrapper]")

                        self.categories = []
                        for item in self.toc:
                            self.categories.extend(item.select("p[role=heading]"))

                        options = [discord.SelectOption(label='None')]
                        for category in self.categories:

                            options.append(discord.SelectOption(
                                label=category.string
                            ))

                        child.options = options

                    if child == self.children[3]:  # choose the docs page
                        category_value = self.children[2].values[0]

                        for category in self.categories:
                            if category.string == category_value:
                                category_section = self.toc[self.categories.index(category)]

                                page_sections = category_section.findChild('ul')
                                self.sections = page_sections.find_all('li', class_="toctree-l1")

                                break

                        options = []
                        self.pages = []
                        if category_value == 'None':
                            options.append(discord.SelectOption(label='None', value=category_value, default=True))

                            # enable the final menu
                            self.children[-1].disabled = False
                            self.children[-1].options = options
                        else:
                            for section in self.sections:
                                page = section.findNext('a')
                                self.pages.append(page)

                                options.append(discord.SelectOption(
                                    label=page.string,
                                    value=page['href']
                                ))

                        child.options = options

                        if category_value == 'None':
                            break

                    if child == self.children[4]:  # choose the docs page section
                        page_value = self.children[3].values[0]

                        if page_value == 'None':
                            options = [discord.SelectOption(label='None', value=page_value, default=True)]
                        else:
                            options = [discord.SelectOption(label='None', value=page_value)]
                            for section in self.sections:
                                page = section.findNext('a')
                                if page_value == page['href']:
                                    page_sections = section.find_all('a')
                                    del page_sections[0]  # delete first item from list

                                    for page_section in page_sections:
                                        options.append(discord.SelectOption(
                                            label=page_section.string,
                                            value=page_section['href']
                                        ))

                        child.options = options

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
            self.docs_version = self.children[1].values[0]

            if self.children[2].values[0] == 'None':
                self.docs_category = ''
                self.docs_page = ''
                self.docs_section = ''
            else:
                self.docs_category = self.children[2].values[0]
                self.docs_page = self.children[3].values[0] if self.children[3].values[0] != 'None' else ''
                self.docs_section = self.children[4].values[0] if self.children[4].values[0] != 'None' else ''
        except IndexError:
            pass
        if select == self.children[0]:  # chose the docs project
            self.docs_version = None
            self.docs_category = None
            self.docs_page = None
            self.docs_section = None
        elif select == self.children[1]:  # chose the docs version
            self.docs_category = None
            self.docs_page = None
            self.docs_section = None
        elif select == self.children[2]:  # chose the docs category
            self.docs_page = None if self.children[2].values[0] != 'None' else ''
            self.docs_section = None if self.children[2].values[0] != 'None' else ''
        elif select == self.children[3]:  # chose the docs page
            self.docs_section = None

        complete, embed = self.check_completion_status()

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

    @discord.ui.select(
        placeholder="Choose category...",
        disabled=True,
        min_values=1,
        max_values=1,
        options=[discord.SelectOption(label='error')]
    )
    async def category_callback(self, select: Select, interaction: discord.Interaction):
        await self.callback(select=select, interaction=interaction)

    @discord.ui.select(
        placeholder="Choose page...",
        disabled=True,
        min_values=1,
        max_values=1,
        options=[discord.SelectOption(label='error')]
    )
    async def page_callback(self, select: Select, interaction: discord.Interaction):
        await self.callback(select=select, interaction=interaction)

    @discord.ui.select(
        placeholder="Choose section...",
        disabled=True,
        min_values=1,
        max_values=1,
        options=[discord.SelectOption(label='error')]
    )
    async def section_callback(self, select: Select, interaction: discord.Interaction):
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

        self.donation_methods = dict(
            github=dict(
                name='GitHub',
                url='https://github.com/sponsors/LizardByte'
            ),
            mee6=dict(
                name='MEE6',
                url='https://mee6.xyz/m/804382334370578482'
            ),
            patreon=dict(
                name='Patreon',
                url='https://www.patreon.com/LizardByte'
            ),
            paypal=dict(
                name='PayPal',
                url='https://paypal.me/ReenigneArcher'
            )
        )

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
