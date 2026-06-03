# lib imports
import discord
import pytest

# local imports
from src.discord_bot import views


class FakeSelect:
    def __init__(self, *, values=None, options=None):
        self.values = values or []
        self.options = options or []
        self.disabled = False


def docs_view(children):
    view = views.DocsCommandView.__new__(views.DocsCommandView)
    view.children = children
    view.interaction = None
    view.docs_project = None
    view.docs_version = None
    view.project_value_map = {'sunshine-0': 'Sunshine'}
    return view


def version_payload():
    return [
        {
            'slug': 'stable',
            'active': True,
            'built': True,
            'type': 'branch',
            'urls': {'documentation': 'https://docs.example.com/stable'},
        },
        {
            'slug': 'inactive',
            'active': False,
            'built': True,
            'type': 'branch',
            'urls': {'documentation': 'https://docs.example.com/inactive'},
        },
        {
            'slug': 'unbuilt',
            'active': True,
            'built': False,
            'type': 'branch',
            'urls': {'documentation': 'https://docs.example.com/unbuilt'},
        },
    ]


@pytest.mark.asyncio
async def test_callback_updates_project_select(mocker):
    project_select = FakeSelect(
        values=['sunshine-0'],
        options=[
            discord.SelectOption(label='Sunshine', value='sunshine-0'),
            discord.SelectOption(label='Other', value='other-1'),
        ],
    )
    version_select = FakeSelect()
    extra_select = FakeSelect()
    view = docs_view(children=[project_select, version_select, extra_select])
    get_json = mocker.patch('src.discord_bot.views.get_json', return_value=version_payload())
    interaction = mocker.Mock()
    interaction.response.edit_message = mocker.AsyncMock()

    await view.callback(select=project_select, interaction=interaction)

    get_json.assert_called_once_with(url='https://app.lizardbyte.dev/dashboard/readthedocs/versions/Sunshine.json')
    assert project_select.disabled is False
    assert version_select.disabled is False
    assert extra_select.disabled is True
    assert version_select.options[0].label == 'stable'
    assert version_select.options[0].value == 'https://docs.example.com/stable'
    assert project_select.options[0].default is True
    assert project_select.options[1].default is False
    assert view.docs_project == 'sunshine-0'
    assert view.docs_version is None
    interaction.response.edit_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_callback_updates_version_select(mocker):
    project_select = FakeSelect(values=['sunshine-0'])
    version_select = FakeSelect(
        values=['https://docs.example.com/stable'],
        options=[
            discord.SelectOption(label='stable', value='https://docs.example.com/stable'),
            discord.SelectOption(label='latest', value='https://docs.example.com/latest'),
        ],
    )
    view = docs_view(children=[project_select, version_select])
    interaction = mocker.Mock()
    interaction.response.edit_message = mocker.AsyncMock()

    await view.callback(select=version_select, interaction=interaction)

    assert project_select.disabled is False
    assert version_select.disabled is False
    assert version_select.options[0].default is True
    assert version_select.options[1].default is False
    assert view.docs_project == 'sunshine-0'
    assert view.docs_version == 'https://docs.example.com/stable'
    embed = interaction.response.edit_message.await_args.kwargs['embed']
    assert embed.title == 'sunshine-0'
    assert embed.url == 'https://docs.example.com/stable'
