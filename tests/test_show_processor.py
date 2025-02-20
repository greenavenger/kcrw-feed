"""Module to test the processing of Shows."""

from datetime import datetime
import json
import uuid
from typing import Any, Dict

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


class DummySource:
    """Fake for BaseSource"""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        # Not used in ShowProcessor, but provided for completeness.
        self.uses_sitemap = True

    def get_resource(self, path: str) -> Any:
        # If path is not an absolute URL, prepend the base URL.
        if not path.startswith("http"):
            path = self.base_url.rstrip("/") + "/" + path.lstrip("/")
        return fake_get_file(path)

    def relative_path(self, url: str) -> str:
        # For testing, return the URL unchanged.
        return url

    def is_show(self, resource: str) -> bool:
        if "episode" in resource:
            return False
        return True

    def is_episode(self, resource: str) -> bool:
        return not self.is_show(resource)


def fake_get_file(url: str, timeout: int = 10) -> Any:
    """Return content based on resource signature."""
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

# Fixture for ShowProcessor using DummySource


@pytest.fixture(name="fake_processor")
def _fake_processor(monkeypatch: pytest.MonkeyPatch) -> ShowProcessor:
    """Return a ShowProcessor instance with DummySource and a monkeypatched
    source_manager.get_file() to return predetermined content based on the
    URL."""
    dummy_source = DummySource("https://www.testsite.com/")
    sp = ShowProcessor(dummy_source, timeout=5)
    monkeypatch.setattr(source_manager, "get_file", fake_get_file)
    return sp


def test_fetch_show(fake_processor: ShowProcessor):
    """Test that fetch() returns a Show object when given a URL that
    indicates a show."""
    url = "https://www.testsite.com/music/shows/test-show"
    fake_processor.fetch(url)
    result = fake_processor.get_show_by_url(url)
    assert isinstance(result, Show)
    # In our fake setup, the fallback extracts the title from the URL.
    assert result.title == "test-show"
    assert result.uuid == uuid.UUID(FAKE_SHOW_UUID)
    assert result.description == "A description of the test show."


def test_fetch_episode(fake_processor: ShowProcessor):
    """Test that fetch() returns an Episode object when given a URL that
    indicates an episode."""
    url = "https://www.testsite.com/music/shows/test-show/test-episode"
    result = fake_processor.fetch(url)
    assert isinstance(result, Episode)
    assert result.title == "Test Episode Page"
    assert result.uuid == uuid.UUID(FAKE_EPISODE_UUID)
    assert result.show_uuid == uuid.UUID(FAKE_SHOW_UUID)
    # Verify the media URL is correctly set.
    assert result.media_url == "https://www.testsite.com/audio/episode.mp3"
    expected_date = datetime.fromisoformat("2025-04-01T12:00:00")
    assert result.airdate == expected_date


def test_fetch_invalid_structure_falls_back_to_show(fake_processor: ShowProcessor):
    """Test that if the URL structure doesn't match the expected pattern,
    fetch() falls back to treating it as a Show."""
    url = "https://www.testsite.com/invalid/path"
    result = fake_processor.fetch(url)
    assert isinstance(result, Show)
    # Fallback should yield a Show object using fake show HTML.
    assert result.description == "A description of the test show."


def test_deduplication(fake_processor: ShowProcessor):
    """Test that _dedup_by_uuid() correctly deduplicates episodes."""
    dt = datetime.now()
    ep1 = Episode(title="Episode 1", airdate=dt, url="url1",
                  media_url="media1", uuid="uuid1")
    # Duplicate with same UUID.
    ep2 = Episode(title="Episode 2", airdate=dt, url="url2",
                  media_url="media2", uuid="uuid1")
    ep3 = Episode(title="Episode 3", airdate=dt, url="url3",
                  media_url="media3", uuid="uuid2")
    episodes = [ep1, ep2, ep3]
    deduped = fake_processor._dedup_by_uuid(episodes)
    assert len(deduped) == 2
    # The first occurrence for "uuid1" should be preserved.
    assert deduped[0] == ep1
    assert deduped[1] == ep3


def test_no_duplicates(fake_processor: ShowProcessor):
    """Test that _dedup_by_uuid() returns all episodes when there
    are no duplicates."""
    dt = datetime.now()
    ep1 = Episode(title="Episode 1", airdate=dt, url="url1",
                  media_url="media1", uuid="uuid1")
    ep2 = Episode(title="Episode 2", airdate=dt, url="url2",
                  media_url="media2", uuid="uuid2")
    episodes = [ep1, ep2]
    deduped = fake_processor._dedup_by_uuid(episodes)
    assert len(deduped) == 2


def test_none_uuid(fake_processor: ShowProcessor):
    """Test that episodes with no UUID are all included."""
    dt = datetime.now()
    ep1 = Episode(title="Episode 1", airdate=dt, url="url1",
                  media_url="media1", uuid=None)
    ep2 = Episode(title="Episode 2", airdate=dt, url="url2",
                  media_url="media2", uuid=None)
    episodes = [ep1, ep2]
    deduped = fake_processor._dedup_by_uuid(episodes)
    assert len(deduped) == 2


def test_mix_of_none_and_duplicates(fake_processor: ShowProcessor):
    """Test deduplication on a mix of episodes with None and duplicate UUIDs."""
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
    # Expected: first occurrence of "uuid1", both episodes with None, and "uuid2"
    assert len(deduped) == 4
    assert deduped[0] == ep1
    assert deduped[1] == ep2
    assert deduped[2] == ep4
    assert deduped[3] == ep5


def test_dedup_homogeneous_episodes(fake_processor: ShowProcessor):
    dt = datetime.now()
    ep1 = Episode(title="Episode 1", airdate=dt, url="url1",
                  media_url="media1", uuid="uuid1")
    ep2 = Episode(title="Episode 2", airdate=dt, url="url2",
                  media_url="media2", uuid="uuid1")
    ep3 = Episode(title="Episode 3", airdate=dt, url="url3",
                  media_url="media3", uuid="uuid2")
    episodes = [ep1, ep2, ep3]
    deduped = fake_processor._dedup_by_uuid(episodes)
    assert len(deduped) == 2
    assert deduped[0] == ep1
    assert deduped[1] == ep3


def test_dedup_homogeneous_hosts(fake_processor: ShowProcessor):
    # Assuming Host is defined with at least uuid and name.
    h1 = Host(uuid="host1", name="Alice")
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
    h = Host(uuid="host1", name="Alice")
    with pytest.raises(AssertionError, match="Mixed types provided to _dedup_by_uuid"):
        fake_processor._dedup_by_uuid([ep, h])
