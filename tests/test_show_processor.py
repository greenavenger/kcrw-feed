"""Module to test the processing of shows"""

from datetime import datetime
import json
from typing import Any, Dict
import uuid

import pytest

from kcrw_feed.show_processor import ShowProcessor
from kcrw_feed.models import Show, Episode, Host
from kcrw_feed import source_manager

# Fake microdata HTML for a Show page.
FAKE_SHOW_UUID = "c5bb1ae9-fd3a-4995-9e78-33e377cc8e78"
FAKE_SHOW_HTML = f"""
<html>
  <head>
    <title>Test Show Page</title>
  </head>
  <body itemscope itemtype="http://schema.org/RadioSeries" itemid="{FAKE_SHOW_UUID}">
    <span itemprop="name">Test Radio Show</span>
    <meta itemprop="description" content="A description of the test show." />
  </body>
</html>
"""

# Fake microdata HTML for an Episode page.
FAKE_EPISODE_UUID = "131dc7f8-4da9-4c31-9a12-ae8de925d309"
FAKE_EPISODE_HTML = f"""
<html>
  <head>
    <title>Test Episode Page</title>
  </head>
  <body itemscope itemtype="http://schema.org/NewsArticle" itemid="{FAKE_EPISODE_UUID}">
    <span itemprop="name">Test Episode</span>
    <meta itemprop="identifier" content="{FAKE_EPISODE_UUID}" />
    <meta itemprop="description" content="A description of the test episode." />
    <link itemprop="contentUrl" href="https://www.testsite.com/audio/episode.mp3" />
    <meta itemprop="datePublished" content="2025-04-01T12:00:00" />
  </body>
</html>
"""

# Fake JSON for an episode player, used by _fetch_episode.
FAKE_EPISODE_JSON: Dict[str, Any] = {
    "title": "Test Episode Page",
    "airdate": "2025-04-01T12:00:00",
    "url": "https://www.testsite.com/music/shows/test-show/test-episode",
    "media": [{"url": "https://www.testsite.com/audio/episode.mp3"}],
    "uuid": FAKE_EPISODE_UUID,
    "show_uuid": FAKE_SHOW_UUID,
    "hosts": [{"uuid": "host-uuid-111"}],
    "html_description": "A description of the test episode.",
    "songlist": "Song A, Song B",
    "image": "https://www.testsite.com/image.jpg",
    "content_type": "audio/mpeg",
    "duration": 3600,
    "ending": "2025-04-01T13:00:00",
    "modified": "2025-04-01T12:05:00"
}


@pytest.fixture(name="fake_processor")
def _fake_processor(monkeypatch: pytest.MonkeyPatch) -> ShowProcessor:
    """
    Return a ShowProcessor instance with source_manager.get_file() monkeypatched to return
    predetermined content based on the URL.

    The fake function returns:
      - FAKE_EPISODE_JSON (as JSON-encoded bytes) when the URL indicates an episode page.
      - FAKE_EPISODE_HTML if "episode" is in the URL (as a fallback).
      - FAKE_SHOW_HTML for show pages.

    This setup works in both development (using local files) and production mode.
    """
    sp = ShowProcessor(timeout=5)

    def fake_get_file(url: str, timeout: int = 10):
        # If the URL indicates a player JSON file for an episode.
        if url.endswith("player.json"):
            return json.dumps(FAKE_EPISODE_JSON).encode("utf-8")
        # If the URL indicates an episode page.
        if "episode" in url:
            return FAKE_EPISODE_HTML.encode("utf-8")
        # Otherwise, assume it's a show page.
        if "test-show" in url:
            return FAKE_SHOW_HTML.encode("utf-8")
        # Default fallback.
        return FAKE_SHOW_HTML.encode("utf-8")

    monkeypatch.setattr(source_manager, "get_file", fake_get_file)
    return sp


def test_fetch_show(fake_processor: ShowProcessor):
    """
    Test that fetch() returns a Show object when given a URL that indicates a show.
    """
    url = "https://www.testsite.com/music/shows/test-show"
    fake_processor.fetch(url)
    result = fake_processor.get_show_by_url(url)
    assert isinstance(result, Show)
    # TODO: Should we take the title from the url or the html?
    # assert result.title == "Test Radio Show"
    assert result.title == "test-show"
    assert result.uuid == uuid.UUID(FAKE_SHOW_UUID)
    assert result.description == "A description of the test show."


def test_fetch_episode(fake_processor: ShowProcessor):
    """
    Test that fetch() returns an Episode object when given a URL that indicates an episode.
    """
    url = "https://www.testsite.com/music/shows/test-show/test-episode"
    result = fake_processor.fetch(url)
    assert isinstance(result, Episode)
    assert result.title == "Test Episode Page"
    assert result.uuid == uuid.UUID(FAKE_EPISODE_UUID)
    assert result.show_uuid == uuid.UUID(FAKE_SHOW_UUID)
    # In our fake JSON, the media URL is provided.
    assert result.media_url == "https://www.testsite.com/audio/episode.mp3"
    # Check that the air date is parsed correctly.
    expected_date = datetime.fromisoformat("2025-04-01T12:00:00")
    assert result.airdate == expected_date


def test_fetch_invalid_structure_falls_back_to_show(fake_processor: ShowProcessor):
    """
    Test that if the URL structure doesn't match the expected pattern,
    fetch() falls back to treating it as a Show.
    """
    url = "https://www.testsite.com/invalid/path"
    result = fake_processor.fetch(url)
    assert isinstance(result, Show)
    # Fallback should yield a Show object using fake show HTML.
    # TODO: see title question above
    # assert result.title == "Test Radio Show"
    assert result.description == "A description of the test show."


def test_deduplication(fake_processor: ShowProcessor):
    """
    Test that _dedup_by_uuid() correctly deduplicates episodes.
    """
    dt = datetime.now()
    ep1 = Episode(title="Episode 1", airdate=dt, url="url1",
                  media_url="media1", uuid="uuid1")
    ep2 = Episode(title="Episode 2", airdate=dt, url="url2",
                  media_url="media2", uuid="uuid1")  # Duplicate
    ep3 = Episode(title="Episode 3", airdate=dt, url="url3",
                  media_url="media3", uuid="uuid2")
    episodes = [ep1, ep2, ep3]
    deduped = fake_processor._dedup_by_uuid(episodes)
    assert len(deduped) == 2
    # Verify that the first occurrence of "uuid1" is preserved.
    assert deduped[0] == ep1
    assert deduped[1] == ep3


def test_no_duplicates(fake_processor: ShowProcessor):
    """
    Test that _dedup_by_uuid() returns all episodes when there are no duplicates.
    """
    dt = datetime.now()
    ep1 = Episode(title="Episode 1", airdate=dt, url="url1",
                  media_url="media1", uuid="uuid1")
    ep2 = Episode(title="Episode 2", airdate=dt, url="url2",
                  media_url="media2", uuid="uuid2")
    episodes = [ep1, ep2]
    deduped = fake_processor._dedup_by_uuid(episodes)
    assert len(deduped) == 2


def test_none_uuid(fake_processor: ShowProcessor):
    """
    Test that episodes with no UUID are all included.
    """
    dt = datetime.now()
    ep1 = Episode(title="Episode 1", airdate=dt, url="url1",
                  media_url="media1", uuid=None)
    ep2 = Episode(title="Episode 2", airdate=dt, url="url2",
                  media_url="media2", uuid=None)
    episodes = [ep1, ep2]
    deduped = fake_processor._dedup_by_uuid(episodes)
    assert len(deduped) == 2


def test_mix_of_none_and_duplicates(fake_processor: ShowProcessor):
    """
    Test deduplication on a mix of episodes with None and duplicate UUIDs.
    """
    dt = datetime.now()
    ep1 = Episode(title="Episode 1", airdate=dt, url="url1",
                  media_url="media1", uuid="uuid1")
    ep2 = Episode(title="Episode 2", airdate=dt, url="url2",
                  media_url="media2", uuid=None)
    ep3 = Episode(title="Episode 3", airdate=dt, url="url3",
                  media_url="media3", uuid="uuid1")
    ep4 = Episode(title="Episode 4", airdate=dt, url="url4",
                  media_url="media4", uuid="uuid2")
    ep5 = Episode(title="Episode 5", airdate=dt, url="url5",
                  media_url="media5", uuid=None)
    episodes = [ep1, ep2, ep3, ep4, ep5]
    deduped = fake_processor._dedup_by_uuid(episodes)
    # Expect ep1 (first uuid "uuid1"), ep2 (None), ep4 (uuid2), and ep5 (None).
    assert len(deduped) == 4
    assert deduped[0] == ep1
    assert deduped[1] == ep2
    assert deduped[2] == ep4
    assert deduped[3] == ep5


def test_dedup_homogeneous_episodes(fake_processor: ShowProcessor):
    dt = datetime.now()
    ep1 = Episode(title="Episode 1", airdate=dt, url="url1",
                  media_url="media1", uuid="uuid1")
    # Duplicate uuid; should be dropped.
    ep2 = Episode(title="Episode 2", airdate=dt, url="url2",
                  media_url="media2", uuid="uuid1")
    ep3 = Episode(title="Episode 3", airdate=dt, url="url3",
                  media_url="media3", uuid="uuid2")
    episodes = [ep1, ep2, ep3]
    deduped = fake_processor._dedup_by_uuid(episodes)
    assert len(deduped) == 2
    # Expect the first instance with "uuid1" to be kept.
    assert deduped[0] == ep1
    assert deduped[1] == ep3


def test_dedup_homogeneous_hosts(fake_processor: ShowProcessor):
    # Assuming you have a Host dataclass with at least a uuid attribute:
    h1 = Host(uuid="host1", name="Alice")
    # Duplicate host should be deduped.
    h2 = Host(uuid="host1", name="Alice")
    h3 = Host(uuid="host2", name="Bob")
    hosts = [h1, h2, h3]
    deduped = fake_processor._dedup_by_uuid(hosts)
    assert len(deduped) == 2
    assert deduped[0] == h1
    assert deduped[1] == h3


def test_mixed_types_dedup(fake_processor: ShowProcessor):
    dt = datetime.now()
    ep = Episode(title="Episode 1", airdate=dt, url="url1",
                 media_url="media1", uuid="uuid1")
    # Create a Host instance (assuming Host is defined similarly).
    h = Host(uuid="host1", name="Alice")
    # When mixing types, our type check should trigger an AssertionError.
    with pytest.raises(AssertionError, match="Mixed types provided to _dedup_by_uuid"):
        fake_processor._dedup_by_uuid([ep, h])
