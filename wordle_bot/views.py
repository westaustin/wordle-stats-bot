from collections.abc import Awaitable, Callable

import discord

from wordle_bot import config

Render = Callable[[int], Awaitable[discord.Embed]]


def pager_states(page: int, pages: int) -> tuple[bool, bool, bool, bool]:
    """Disabled flags for ⏮ ◀ ▶ ⏭."""
    at_start, at_end = page <= 0, page >= pages - 1
    return at_start, at_start, at_end, at_end


class OwnedView(discord.ui.View):
    """Buttons only the person who ran the command can press."""

    def __init__(self, owner_id: int):
        super().__init__(timeout=config.VIEW_TIMEOUT)
        self.owner_id = owner_id
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Run the command yourself to browse.", ephemeral=True)
        return False

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    async def _show(self, interaction: discord.Interaction, embed_coro: Awaitable[discord.Embed]):
        # Defer first: rendering may fetch up to a page of answers, longer than Discord's 3s window.
        await interaction.response.defer()
        await interaction.edit_original_response(embed=await embed_coro, view=self)


class HistoryView(OwnedView):
    def __init__(self, owner_id: int, pages: int, render: Render):
        super().__init__(owner_id)
        self.pages, self.render, self.page = pages, render, 0
        self._buttons = []
        for label, target in [("⏮", lambda: 0), ("◀", lambda: self.page - 1),
                              ("▶", lambda: self.page + 1), ("⏭", lambda: self.pages - 1)]:
            button = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary)
            button.callback = self._make_callback(target)
            self.add_item(button)
            self._buttons.append(button)
        self._refresh()

    def _make_callback(self, target: Callable[[], int]):
        async def callback(interaction: discord.Interaction):
            await self.go_to(interaction, target())
        return callback

    def _refresh(self):
        for button, disabled in zip(self._buttons, pager_states(self.page, self.pages)):
            button.disabled = disabled

    async def go_to(self, interaction: discord.Interaction, page: int):
        self.page = max(0, min(page, self.pages - 1))
        self._refresh()
        await self._show(interaction, self.render(self.page))


class DayView(OwnedView):
    def __init__(self, owner_id: int, wordle_no: int, latest_no: int, render: Render):
        super().__init__(owner_id)
        self.wordle_no, self.latest_no, self.render = wordle_no, latest_no, render
        self.prev_button = discord.ui.Button(style=discord.ButtonStyle.secondary)
        self.next_button = discord.ui.Button(style=discord.ButtonStyle.secondary)
        self.prev_button.callback = self._make_callback(-1)
        self.next_button.callback = self._make_callback(+1)
        self.add_item(self.prev_button)
        self.add_item(self.next_button)
        self._refresh()

    def _make_callback(self, step: int):
        async def callback(interaction: discord.Interaction):
            await self.go_to(interaction, self.wordle_no + step)
        return callback

    def _refresh(self):
        n = self.wordle_no
        self.prev_button.label = f"◀ #{n - 1}"
        self.next_button.label = f"#{n + 1} ▶"
        self.prev_button.disabled = n <= 0
        self.next_button.disabled = n + 1 > self.latest_no

    async def go_to(self, interaction: discord.Interaction, wordle_no: int):
        self.wordle_no = max(0, min(wordle_no, self.latest_no))
        self._refresh()
        await self._show(interaction, self.render(self.wordle_no))
