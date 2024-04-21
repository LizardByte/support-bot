# lib imports
import discord


class RefundModal(discord.ui.Modal):
    """
    Class representing `discord.ui.Modal` for ``refund`` slash command.
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.add_item(discord.ui.InputText(label="Name"))
        self.add_item(discord.ui.InputText(label="Email"))
        self.add_item(discord.ui.InputText(label="Purchase Date"))

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Refund request completed",
                              description="Your refund is being processed!")
        embed.add_field(name="Original price", value="$0.00")
        embed.add_field(name="Refund amount", value="$0.00")
        await interaction.response.send_message(embeds=[embed])
