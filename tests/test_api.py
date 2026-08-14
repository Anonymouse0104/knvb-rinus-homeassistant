from pathlib import Path

from custom_components.rinus_knvb.api import extract_craft_session, extract_next_data


SAMPLE = Path("/mnt/data/markdown(4).md geplakt").read_text()


def test_extract_next_data():
    data = extract_next_data(SAMPLE)
    assert data["props"]["pageProps"]["pageTitle"] == "Kalender"
    assert len(data["props"]["pageProps"]["items"]) == 161


def test_extract_craft_session():
    assert extract_craft_session("foo=bar; CraftSessionId=abc123; baz=qux") == "abc123"
    assert extract_craft_session("abc123") == "abc123"
