"""Module to test the state management component."""

import io
import json
from datetime import datetime
import pytest
from typing import Dict, Any, IO

from kcrw_feed.state_manager import Json
from kcrw_feed.models import Host, Show, Episode


def test_default_serializer_datetime():
    js = Json()
    dt = datetime(2025, 1, 1, 12, 30)
    result = js.default_serializer(dt)
    assert result == dt.isoformat()


def test_default_serializer_invalid():
    js = Json()
    with pytest.raises(TypeError):
        js.default_serializer(123)  # An int should raise TypeError


def test_parse_datetime():
    js = Json()
    dt_str = "2025-01-01T12:30:00"
    dt = js._parse_datetime(dt_str)
    expected = datetime(2025, 1, 1, 12, 30)
    assert dt == expected


def test_host_from_dict():
    js = Json()
    host_data = {
        "name": "Host 1",
    }
    host = js.host_from_dict(host_data)
    assert isinstance(host, Host)
    assert host.name == "Host 1"


def test_episode_from_dict():
    js = Json()
    dt_str = "2025-01-01T12:30:00"
    data = {
        "title": "Episode 1",
        "airdate": dt_str,
        "url": "http://example.com/episode1",
        "media_url": "http://example.com/episode1.mp3",
        "description": "Test episode"
    }
    episode = js.episode_from_dict(data)
    assert isinstance(episode, Episode)
    assert episode.title == "Episode 1"
    assert episode.url == "http://example.com/episode1"
    assert episode.media_url == "http://example.com/episode1.mp3"
    assert episode.description == "Test episode"
    assert episode.airdate == datetime.fromisoformat(dt_str)


def test_show_from_dict():
    js = Json()
    dt_str = "2025-01-02T13:45:00"
    show_data = {
        "title": "Show 1",
        "url": "http://example.com/show1",
        "description": "Test show",
        "last_updated": dt_str,
        "metadata": {"genre": "rock"},
        "hosts": [
            {
                "name": "Host 1"
            }
        ],
        "episodes": [
            {
                "title": "Episode A",
                "airdate": "2025-01-01T12:30:00",
                "url": "http://example.com/episode1",
                "media_url": "http://example.com/episodeA.mp3",
                "description": "Episode A desc"
            }
        ]
    }
    show = js.show_from_dict(show_data)
    assert isinstance(show, Show)
    assert show.title == "Show 1"
    assert show.url == "http://example.com/show1"
    assert show.description == "Test show"
    assert show.metadata == {"genre": "rock"}
    assert show.last_updated == datetime.fromisoformat(dt_str)
    assert len(show.hosts) == 1
    ho = show.hosts[0]
    assert ho.name == "Host 1"
    assert len(show.episodes) == 1
    ep = show.episodes[0]
    assert ep.title == "Episode A"


@pytest.fixture(name="fake_fs")
# Hermetic: Test file ops without actually touching local disk
def _fake_fs(monkeypatch: pytest.MonkeyPatch) -> Dict[str, str]:
    """
    A simple fake file system using a dictionary.
    Files written to 'open' in write mode will be stored in the dictionary.
    Reads will return a StringIO initialized with the stored contents.
    """
    files: Dict[str, str] = {}

    def fake_open(filename: str, mode: str = 'r', *args: Any, **kwargs: Any) -> IO[str]:
        # For writing: create a StringIO and store its contents when closed.
        if 'w' in mode:
            file_obj = io.StringIO()

            # Override close to store the file content
            orig_close = file_obj.close

            def fake_close() -> None:
                files[filename] = file_obj.getvalue()
                orig_close()
            file_obj.close = fake_close
            return file_obj

        # For reading: return a StringIO containing the file's content (or empty string if not found).
        elif 'r' in mode:
            content = files.get(filename, '')
            return io.StringIO(content)

        else:
            raise ValueError(f"Unsupported file mode: {mode}")

    monkeypatch.setattr("builtins.open", fake_open)
    return files


def test_save_and_load_state_in_memory(fake_fs: Dict[str, str]):
    """Create test data: a Host with one Show and one Episode"""
    dt1 = datetime(2025, 1, 1, 12, 30)
    dt2 = datetime(2025, 1, 2, 13, 45)
    host = Host(
        name="Host 1"
    )
    episode = Episode(
        title="Episode A",
        airdate=dt1,
        url="http://example.com/episodeA",
        media_url="http://example.com/episodeA.mp3",
        description="Episode A desc"
    )
    show = Show(
        title="Show 1",
        url="http://example.com/show1",
        description="Test show",
        hosts=[host],
        episodes=[episode],
        last_updated=dt2,
        metadata={"genre": "rock"}
    )

    # Use a fake filename; it doesn't matter what string we choose.
    fake_filename = "fake_state.json"
    js = Json(filename=fake_filename)

    # Save state (this will write to our fake_fs dictionary)
    js.save_state(show)
    # Optionally, inspect fake_fs to see the file content.
    saved_content = fake_fs[fake_filename]
    # For example, check that the saved content is valid JSON.
    data = json.loads(saved_content)
    assert data["title"] == "Show 1"
    assert len(data["hosts"]) == 1
    assert len(data["episodes"]) == 1
    # Load state (this will read from fake_fs)
    loaded_show = js.load_state()
    # Check that the show details match.
    assert len(loaded_show.hosts) == len(show.hosts)
    assert loaded_show.title == show.title
    assert loaded_show.url == show.url
    assert loaded_show.description == show.description
    assert loaded_show.metadata == show.metadata
    # Compare datetime fields by their ISO strings.
    assert loaded_show.last_updated.isoformat(
    ) == show.last_updated.isoformat()
    # Check that the host details match.
    assert loaded_show.title == show.title
    # Verify episode data.
    assert len(loaded_show.episodes) == 1
    loaded_episode = loaded_show.episodes[0]
    original_episode = show.episodes[0]
    assert loaded_episode.title == original_episode.title
    assert loaded_episode.media_url == original_episode.media_url
    assert loaded_episode.description == original_episode.description
    assert loaded_episode.airdate.isoformat() == original_episode.airdate.isoformat()
