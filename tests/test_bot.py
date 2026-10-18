from types import SimpleNamespace

from wordle_bot.bot import display_name


def test_display_name_fallback():
    gone = SimpleNamespace(get_member=lambda uid: None)
    assert display_name(gone, 42) == "Former member (42)"
    here = SimpleNamespace(get_member=lambda uid: SimpleNamespace(display_name="snowMAMA"))
    assert display_name(here, 42) == "snowMAMA"
