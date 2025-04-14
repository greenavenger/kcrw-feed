"""Module to test the state management component."""

from datetime import datetime
import io
import json
import os
from typing import Dict
import atomicwrites
import uuid

import pytest

from kcrw_feed.persistence.state import StatePersister
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
        "image": "https://example.com/big-image",
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


def test_save_and_load_state(tmp_path):
    """Create test data, persist it as a ShowDirectory,
    then load it back and verify the state round-trips correctly."""
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
        image="https://example.com/big-image",
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
    # Use tmp_path to create an isolated temporary file.
    fake_filename = tmp_path / TEST_FILE
    persister = StatePersister(storage_root=str(
        tmp_path), state_file=str(fake_filename))

    # Save the state to the temporary file.
    persister.save(directory, str(fake_filename))
    # Read the JSON content back.
    saved_content = fake_filename.read_text(encoding="utf-8")
    data = json.loads(saved_content)
    # Check that the top-level key "shows" exists and has one entry.
    assert "shows" in data
    assert len(data["shows"]) == 1
    saved_show = data["shows"][0]
    assert saved_show["title"] == "Show 1"
    assert len(saved_show["hosts"]) == 1
    assert len(saved_show["episodes"]) == 1

    # Load state from the temporary file.
    loaded_directory = persister.load(str(fake_filename))
    loaded_show = loaded_directory.shows[0]
    assert loaded_show.title == show.title
    assert loaded_show.url == show.url
    assert loaded_show.description == show.description
    assert loaded_show.metadata == show.metadata
    # Compare datetime fields by ISO string.
    assert loaded_show.last_updated.isoformat() == show.last_updated.isoformat()
    assert len(loaded_show.hosts) == len(show.hosts)
    assert len(loaded_show.episodes) == 1
    loaded_episode = loaded_show.episodes[0]
    original_episode = show.episodes[0]
    assert loaded_episode.title == original_episode.title
    assert loaded_episode.media_url == original_episode.media_url
    assert loaded_episode.description == original_episode.description
    assert loaded_episode.airdate.isoformat() == original_episode.airdate.isoformat()
