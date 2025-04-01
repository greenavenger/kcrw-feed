"""Module to test the state management component."""

from typing import Dict
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import io
import json
import os
import tempfile
from typing import Dict, Any
import uuid
import xml.etree.ElementTree as ET

import pytest

from kcrw_feed.persistence.manager import StatePersister, FeedPersister
from kcrw_feed.models import Host, Show, Episode, Resource, ShowDirectory

TEST_FILE = "test_kcrw_feed.json"


def test_default_serializer_datetime(tmp_path):
    js = StatePersister(storage_root=tmp_path, state_file=TEST_FILE)
    dt = datetime(2025, 1, 1, 12, 30)
    result = js.default_serializer(dt)
    assert result == dt.isoformat()


def test_default_serializer_invalid(tmp_path):
    js = StatePersister(storage_root=tmp_path, state_file=TEST_FILE)
    with pytest.raises(TypeError):
        js.default_serializer(123)  # An int should raise TypeError


def test_parse_datetime(tmp_path):
    js = StatePersister(storage_root=tmp_path, state_file=TEST_FILE)
    dt_str = "2025-01-01T12:30:00"
    dt = js._parse_datetime(dt_str)
    expected = datetime(2025, 1, 1, 12, 30)
    assert dt == expected


def test_host_from_dict(tmp_path):
    js = StatePersister(storage_root=tmp_path, state_file=TEST_FILE)
    host_data = {
        "name": "Host 1",
        "uuid": "a690aae0-c48d-4771-ac88-0fe13a730b7b"
    }
    host = js.host_from_dict(host_data)
    assert host.name == "Host 1"
    # When the uuid is provided as a string, _parse_uuid is applied.
    assert host.uuid == uuid.UUID("a690aae0-c48d-4771-ac88-0fe13a730b7b")


def test_episode_from_dict(tmp_path):
    js = StatePersister(storage_root=tmp_path, state_file=TEST_FILE)
    dt_str = "2025-01-01T12:30:00"
    url = "http://example.com/episode1"
    data = {
        "title": "Episode 1",
        "airdate": dt_str,
        "last_updated": dt_str,
        "uuid": "2709247f-7bb7-4af9-a6c0-b2632e009e9b",
        "show_uuid": "d4e287b6-2340-41fb-99c3-9bdbac22fd1f",
        "url": url,
        "media_url": "http://example.com/episode1.mp3",
        "description": "Test episode",
        "resource": {
            "url": url,
            "metadata": {
                "lastmod": dt_str
            }
        }
    }
    episode = js.episode_from_dict(data)
    assert episode.title == "Episode 1"
    assert episode.url == "http://example.com/episode1"
    assert episode.media_url == "http://example.com/episode1.mp3"
    assert episode.description == "Test episode"
    assert episode.airdate == datetime.fromisoformat(dt_str)
    assert episode.last_updated == datetime.fromisoformat(dt_str)
    assert episode.uuid == uuid.UUID("2709247f-7bb7-4af9-a6c0-b2632e009e9b")
    assert episode.show_uuid == uuid.UUID(
        "d4e287b6-2340-41fb-99c3-9bdbac22fd1f")


def test_show_from_dict(tmp_path):
    js = StatePersister(storage_root=tmp_path, state_file=TEST_FILE)
    dt_str = "2025-01-02T13:45:00"
    airdate = "2025-01-01T12:30:00"
    show_url = "http://example.com/show1"
    episode_url = "http://example.com/episodeA"
    show_data = {
        "title": "Show 1",
        "url": show_url,
        "uuid": "d4e287b6-2340-41fb-99c3-9bdbac22fd1f",
        "description": "Test show",
        "last_updated": dt_str,
        "metadata": {"genre": "rock"},
        "hosts": [
            {
                "name": "Host 1",
                "uuid": "a690aae0-c48d-4771-ac88-0fe13a730b7b"
            }
        ],
        "episodes": [
            {
                "title": "Episode A",
                "airdate": airdate,
                "last_updated": airdate,
                "uuid": "2709247f-7bb7-4af9-a6c0-b2632e009e9b",
                "show_uuid": "d4e287b6-2340-41fb-99c3-9bdbac22fd1f",
                "url": episode_url,
                "media_url": "http://example.com/episodeA.mp3",
                "description": "Episode A desc",
                "resource": {
                    "url": show_url,
                    "metadata": {
                        "lastmod": dt_str
                    }
                }
            }
        ],
        "resource": {
            "url": show_url,
            "metadata": {
                "lastmod": dt_str
            }
        }
    }
    show = js.show_from_dict(show_data)
    assert show.title == "Show 1"
    assert show.url == "http://example.com/show1"
    assert show.description == "Test show"
    assert show.metadata == {"genre": "rock"}
    assert show.last_updated == datetime.fromisoformat(dt_str)
    assert len(show.hosts) == 1
    assert show.hosts[0].name == "Host 1"
    assert len(show.episodes) == 1
    assert show.episodes[0].title == "Episode A"


@pytest.fixture(name="fake_fs")
def fake_fs_fixture(monkeypatch: pytest.MonkeyPatch) -> Dict[str, str]:
    """
    A fake file system that intercepts open calls.
    Files written in 'w' or 'wb' mode are stored in a dictionary.
    Reads return a StringIO or BytesIO initialized with the stored content.
    Also patches os.path.exists to use this fake file system.
    """
    files: Dict[str, str] = {}

    def fake_open(filename: str, mode: str = "r", *args, **kwargs):
        if "w" in mode:
            if "b" in mode:
                # Binary write mode: use BytesIO.
                file_obj = io.BytesIO()
                orig_close = file_obj.close

                def fake_close():
                    # Store the written bytes as a UTF-8 string.
                    files[filename] = file_obj.getvalue().decode("utf-8")
                    orig_close()
                file_obj.close = fake_close
                return file_obj
            else:
                # Text write mode: use StringIO.
                file_obj = io.StringIO()
                orig_close = file_obj.close

                def fake_close():
                    files[filename] = file_obj.getvalue()
                    orig_close()
                file_obj.close = fake_close
                return file_obj
        elif "r" in mode:
            content = files.get(filename, "")
            if "b" in mode:
                return io.BytesIO(content.encode("utf-8"))
            else:
                return io.StringIO(content)
        else:
            raise ValueError(f"Unsupported file mode: {mode}")

    monkeypatch.setattr("builtins.open", fake_open)
    # Patch os.path.exists to check our fake_fs dict.
    monkeypatch.setattr(os.path, "exists", lambda filename: filename in files)
    return files


def test_save_and_load_state_in_memory(fake_fs: Dict[str, str]):
    """Create test data: a Host with one Show and one Episode, persist it
    as a ShowDirectory, then load it back and verify that the state
    round-trips correctly."""
    dt1 = datetime(2025, 1, 1, 12, 30)
    dt2 = datetime(2025, 1, 2, 13, 45)

    host = Host(
        name="Host 1",
        uuid=uuid.UUID("a690aae0-c48d-4771-ac88-0fe13a730b7b")
    )
    episode = Episode(
        title="Episode A",
        airdate=dt1,
        last_updated=dt1,
        uuid=uuid.UUID("2709247f-7bb7-4af9-a6c0-b2632e009e9b"),
        show_uuid=uuid.UUID("d4e287b6-2340-41fb-99c3-9bdbac22fd1f"),
        url="http://example.com/episodeA",
        media_url="http://example.com/episodeA.mp3",
        description="Episode A desc",
        resource=Resource(
            url="http://example.com/episodeA",
            source="http://example.com/episodeA",
            last_updated=dt1,
            metadata={
                "lastmod": dt1
            }
        )
    )
    show = Show(
        title="Show 1",
        url="http://example.com/show1",
        uuid=uuid.UUID("d4e287b6-2340-41fb-99c3-9bdbac22fd1f"),
        description="Test show",
        hosts=[host],
        episodes=[episode],
        last_updated=dt2,
        resource=Resource(
            url="http://example.com/show1",
            source="http://example.com/show1",
            last_updated=dt2,
            metadata={
                "lastmod": dt2
            }
        ),
        metadata={"genre": "rock"}
    )
    directory = ShowDirectory(shows=[show])
    fake_filename = "fake_state.json"
    persister = StatePersister(storage_root=".", state_file=fake_filename)

    # Save state to the fake file system.
    persister.save(directory, fake_filename)
    saved_content = fake_fs[fake_filename]
    data = json.loads(saved_content)
    # Check that the top-level key "shows" exists and has one entry.
    assert "shows" in data
    assert len(data["shows"]) == 1
    saved_show = data["shows"][0]
    assert saved_show["title"] == "Show 1"
    assert len(saved_show["hosts"]) == 1
    assert len(saved_show["episodes"]) == 1

    # Load state from the fake file system.
    loaded_directory = persister.load(fake_filename)
    loaded_show = loaded_directory.shows[0]
    assert loaded_show.title == show.title
    assert loaded_show.url == show.url
    assert loaded_show.description == show.description
    assert loaded_show.metadata == show.metadata
    # Compare datetime fields by ISO string
    assert loaded_show.last_updated.isoformat() == show.last_updated.isoformat()
    assert len(loaded_show.hosts) == len(show.hosts)
    assert len(loaded_show.episodes) == 1
    loaded_episode = loaded_show.episodes[0]
    original_episode = show.episodes[0]
    assert loaded_episode.title == original_episode.title
    assert loaded_episode.media_url == original_episode.media_url
    assert loaded_episode.description == original_episode.description
    assert loaded_episode.airdate.isoformat() == original_episode.airdate.isoformat()


@pytest.fixture
def dummy_directory() -> ShowDirectory:
    now = datetime.now()
    show1 = Show(
        title="Show One",
        url="https://example.com/show1",
        uuid="11111111-1111-1111-1111-111111111111",
        description="Description for Show One",
        hosts=[],
        episodes=[
            Episode(
                title="Episode 1",
                airdate=now - timedelta(days=1),
                last_updated=now - timedelta(days=1),
                url="https://example.com/show1/ep1",
                media_url="https://example.com/show1/ep1.mp3",
                uuid="a1111111-1111-1111-1111-111111111111",
                description="Episode 1 description"
            ),
            Episode(
                title="Episode 2",
                airdate=now,
                last_updated=now,
                url="https://example.com/show1/ep2",
                media_url="https://example.com/show1/ep2.mp3",
                uuid="a2222222-2222-2222-2222-222222222222",
                description="Episode 2 description"
            )
        ],
        last_updated=now
    )
    show2 = Show(
        title="Show Two",
        url="https://example.com/show2",
        uuid="22222222-2222-2222-2222-222222222222",
        description="Description for Show Two",
        hosts=[],
        episodes=[
            Episode(
                title="Episode A",
                airdate=now - timedelta(days=2),
                last_updated=now - timedelta(days=2),
                url="https://example.com/show2/epa",
                media_url="https://example.com/show2/epa.mp3",
                uuid="b1111111-1111-1111-1111-111111111111",
                description="Episode A description"
            ),
            Episode(
                title="Episode B",
                airdate=now - timedelta(days=1),
                last_updated=now - timedelta(days=1),
                url="https://example.com/show2/epb",
                media_url="https://example.com/show2/epb.mp3",
                uuid="b2222222-2222-2222-2222-222222222222",
                description="Episode B description"
            )
        ],
        last_updated=now - timedelta(days=1)
    )
    return ShowDirectory(shows=[show1, show2])


def test_rss_save_creates_files(dummy_directory):
    rss_persister = FeedPersister(storage_root=".")
    with tempfile.TemporaryDirectory() as tmpdirname:
        rss_persister.save(dummy_directory, tmpdirname)
        # Expect one file per show (i.e. 2 files).
        files = os.listdir(tmpdirname)
        assert len(files) == 2

        for file in files:
            file_path = os.path.join(tmpdirname, file)
            # Parse the XML feed.
            tree = ET.parse(file_path)
            root = tree.getroot()
            # Check that the root element is <rss> and it has a <channel>.
            assert root.tag == "rss"
            channel = root.find("channel")
            assert channel is not None

            # Verify that the channel title is set.
            title = channel.find("title")
            assert title is not None and title.text

            # Verify that items (episodes) exist and their pubDate values are valid.
            items = channel.findall("item")
            pub_dates = [item.find("pubDate").text for item in items if item.find(
                "pubDate") is not None]
            # Convert pubDate strings to datetime objects.
            dates = [parsedate_to_datetime(d) for d in pub_dates]
            # Check that dates are in descending order.
            assert dates == sorted(dates, reverse=True)
