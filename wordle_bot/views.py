import asyncio
import logging
from collections.abc import Awaitable, Callable

import discord

from wordle_bot import config

log = logging.getLogger(__name__)

Render = Callable[[int], Awaitable[discord.Embed]]
Target = int | Callable[[], int]


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
        self._lock = asyncio.Lock()

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

    async def _navigate(self, interaction: discord.Interaction, target: Target):
        """Move to `target` (a position, or a function of the current one).

        Presses run one at a time, so a double-tap moves two steps and the message always matches
        the buttons. State only changes once the interaction is acknowledged.
        """
        async with self._lock:
            try:
                # Defer first: rendering may fetch up to a page of answers, longer than Discord's 3s window.
                await interaction.response.defer()
            except discord.HTTPException as e:
                log.warning("Couldn't acknowledge button press: %s", e)
                return
            position = self._clamp(target() if callable(target) else target)
            embed = await self.render(position)
            self._set_position(position)
            await interaction.edit_original_response(embed=embed, view=self)

    def _clamp(self, position: int) -> int:
        raise NotImplementedError

    def _set_position(self, position: int) -> None:
        raise NotImplementedError


class HistoryView(OwnedView):
    def __init__(self, owner_id: int, pages: int, render: Render):
        super().__init__(owner_id)
        self.pages, self.render, self.page = pages, render, 0
        self._buttons = []
        for label, target in [("⏮", 0), ("◀", lambda: self.page - 1),
                              ("▶", lambda: self.page + 1), ("⏭", lambda: self.pages - 1)]:
            button = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary)
            button.callback = self._make_callback(target)
            self.add_item(button)
            self._buttons.append(button)
        self._refresh()

    def _make_callback(self, target: Target):
        async def callback(interaction: discord.Interaction):
            await self.go_to(interaction, target)
        return callback

    def _refresh(self):
        for button, disabled in zip(self._buttons, pager_states(self.page, self.pages)):
            button.disabled = disabled

    def _clamp(self, page: int) -> int:
        return max(0, min(page, self.pages - 1))

    def _set_position(self, page: int) -> None:
        self.page = page
        self._refresh()

    async def go_to(self, interaction: discord.Interaction, page: Target):
        await self._navigate(interaction, page)


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
            await self.go_to(interaction, lambda: self.wordle_no + step)
        return callback

    def _refresh(self):
        n = self.wordle_no
        self.prev_button.label = f"◀ #{n - 1}"
        self.next_button.label = f"#{n + 1} ▶"
        self.prev_button.disabled = n <= 0
        self.next_button.disabled = n + 1 > self.latest_no

    def _clamp(self, wordle_no: int) -> int:
        return max(0, min(wordle_no, self.latest_no))

    def _set_position(self, wordle_no: int) -> None:
        self.wordle_no = wordle_no
        self._refresh()

    async def go_to(self, interaction: discord.Interaction, wordle_no: Target):
        await self._navigate(interaction, wordle_no)
