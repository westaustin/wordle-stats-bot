import logging
from collections.abc import Awaitable, Callable

import discord

log = logging.getLogger(__name__)

# (interaction, owner id, subject, position) -> the message's new embed and buttons. Registered by
# bot.py: "h" pages a user's history (subject = user id, position = page), "d" moves between
# days (subject unused, position = Wordle #).
Handler = Callable[[discord.Interaction, int, int, int], Awaitable[tuple[discord.Embed, discord.ui.View | None]]]
HANDLERS: dict[str, Handler] = {}


def pager_states(page: int, pages: int) -> tuple[bool, bool, bool, bool]:
    """Disabled flags for ⏮ ◀ ▶ ⏭."""
    at_start, at_end = page <= 0, page >= pages - 1
    return at_start, at_start, at_end, at_end


class PagerButton(discord.ui.DynamicItem[discord.ui.Button],
                  template=r"pg:(?P<kind>[hd]):(?P<slot>\d):(?P<owner>\d+):(?P<subject>\d+):(?P<pos>\d+)"):
    """A paging button that carries its destination in its custom id.

    Nothing is held in memory, so buttons keep working after any amount of time and across
    restarts. Each press goes to the page the button showed when it was drawn, so a double-tap
    lands on the same page twice, and every edit sends an embed with its matching buttons.
    """

    def __init__(self, kind: str, slot: int, owner_id: int, subject: int, position: int,
                 label: str | None = None, disabled: bool = False):
        position = max(position, 0)
        super().__init__(discord.ui.Button(
            label=label, style=discord.ButtonStyle.secondary, disabled=disabled,
            custom_id=f"pg:{kind}:{slot}:{owner_id}:{subject}:{position}"))
        self.kind, self.owner_id, self.subject, self.position = kind, owner_id, subject, position

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["kind"], int(match["slot"]), int(match["owner"]), int(match["subject"]),
                   int(match["pos"]))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Run the command yourself to browse.", ephemeral=True)
        return False

    async def callback(self, interaction: discord.Interaction):
        try:
            # Defer first: rendering may fetch up to a page of answers, longer than Discord's 3s window.
            await interaction.response.defer()
        except discord.HTTPException as e:
            log.warning("Couldn't acknowledge button press: %s", e)
            return
        embed, view = await HANDLERS[self.kind](interaction, self.owner_id, self.subject, self.position)
        await interaction.edit_original_response(embed=embed, view=view)


def history_view(owner_id: int, user_id: int, page: int, pages: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    targets = [0, page - 1, page + 1, pages - 1]
    for slot, (label, target, disabled) in enumerate(zip("⏮◀▶⏭", targets, pager_states(page, pages))):
        view.add_item(PagerButton("h", slot, owner_id, user_id, target, label, disabled))
    return view


def day_view(owner_id: int, wordle_no: int, latest_no: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(PagerButton("d", 0, owner_id, 0, wordle_no - 1, f"◀ #{wordle_no - 1}", wordle_no <= 0))
    view.add_item(PagerButton("d", 1, owner_id, 0, wordle_no + 1, f"#{wordle_no + 1} ▶",
                              wordle_no + 1 > latest_no))
    return view
