"""Module to test the processing of Shows."""

import pytest
import tempfile
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from kcrw_feed.models import Show, Episode, Resource
from kcrw_feed.processing.station import StationProcessor
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
    <meta itemprop="mainEntityOfPage" content="https://www.testsite.com/music/shows/test-show" />
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

# Fake JSON for an episode player (used by _process_episode)
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

FAKE_RESOURCE = Resource(
    url="https://www.testsite.com/music/shows/test-show/foo",
    source="https://www.testsite.com/music/shows/test-show/foo",
    last_updated=datetime.now(),
    metadata={
        "lastmod": datetime.now()
    }
)

# A simple fake implementation of a StationCatalog for testing purposes.


class FakeCatalog:
    def __init__(self):
        self.shows: Dict[str, Show] = {}
        self.episodes: Dict[str, Episode] = {}
        self.resources: Dict[str, Resource] = {}
        self.source = DummySource("https://www.testsite.com/")

    def get_source(self) -> Any:
        return self.source

    def list_shows(self) -> List[Show]:
        return list(self.shows.values())

    def add_show(self, show: Show) -> None:
        if show.uuid is None:
            raise ValueError("Show must have a uuid")
        self.shows[show.uuid] = show

    def list_episodes(self) -> List[Episode]:
        return list(self.episodes.values())

    def add_episode(self, episode: Episode) -> None:
        key = episode.uuid if episode.uuid is not None else episode.url
        self.episodes[key] = episode

    def get_resource(self, url: str) -> Optional[Resource]:
        return self.resources.get(url)

# DummySource from your tests.


class DummySource:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.uses_sitemap = True

    def get_reference(self, path: str) -> Any:
        # If path is not an absolute URL, prepend the base URL.
        if not path.startswith("http"):
            path = self.base_url.rstrip("/") + "/" + path.lstrip("/")
        return fake_get_file(path)

    def relative_path(self, url: str) -> str:
        return url


def fake_get_file(url: str) -> Any:
    """Return content based on resource signature."""
    # For episode player JSON.
    if url.endswith("player.json"):
        return json.dumps(FAKE_EPISODE_JSON).encode("utf-8")
    # If URL indicates an episode page.
    if "test-episode" in url:
        return FAKE_EPISODE_HTML.encode("utf-8")
    # If URL indicates a show page.
    if "test-show" in url:
        return FAKE_SHOW_HTML.encode("utf-8")
    return FAKE_SHOW_HTML.encode("utf-8")


@pytest.fixture(name="fake_processor")
def fake_processor_fixture(monkeypatch: pytest.MonkeyPatch) -> StationProcessor:
    """Create a StationProcessor using a FakeCatalog.
    Monkeypatch the instance of DummySource's _get_file method to return predetermined content.
    """
    fake_catalog = FakeCatalog()
    # Create an instance of DummySource.
    dummy_source = DummySource("https://www.testsite.com/")
    # Patch the instance's _get_file method.
    # monkeypatch.setattr(dummy_source, '_get_file', fake_get_file)
    monkeypatch.setattr(dummy_source, 'get_reference', fake_get_file)
    # Use this dummy_source in your catalog.
    fake_catalog.source = dummy_source

    from kcrw_feed.processing import station  # ensure we import the correct module
    sp = station.StationProcessor(fake_catalog)
    return sp


def test_process_show(fake_processor: StationProcessor):
    """Test that process_resource() returns a Show object when given a
    show URL."""
    url = "https://www.testsite.com/music/shows/test-show"
    resource = Resource(
        url=url,
        source=url,
        last_updated=datetime.now(),
        metadata={"lastmod": datetime.now()}
    )
    result = fake_processor.process_resource(resource)
    print(result)
    # result = fake_processor.catalog.shows.get(FAKE_SHOW_UUID)
    assert result is not None
    assert isinstance(result, Show)
    assert result.title == "test-show"  # "Test Radio Show"
    # UUID should be extracted correctly.
    assert result.uuid == uuid.UUID(FAKE_SHOW_UUID)
    assert result.description == "A description of the test show."


def test_process_episode(fake_processor: StationProcessor):
    """Test that process_resource() returns an Episode object when given
    an episode URL."""
    url = "https://www.testsite.com/music/shows/test-show/test-episode"
    resource = Resource(
        url=url,
        source=url,
        last_updated=datetime.now(),
        metadata={"lastmod": datetime.now()}
    )
    result = fake_processor.process_resource(resource)
    assert isinstance(result, Episode)
    assert result.title == "Test Episode Page"
    assert result.uuid == uuid.UUID(FAKE_EPISODE_UUID)
    # Check that show_uuid is set from the episode data.
    assert result.show_uuid == uuid.UUID(FAKE_SHOW_UUID)
    assert result.media_url == "https://www.testsite.com/audio/episode.mp3"
    expected_date = datetime.fromisoformat("2025-04-01T12:00:00")
    assert result.airdate == expected_date


def test_process_invalid_structure_falls_back_to_show(fake_processor: StationProcessor):
    """Test that an invalid URL structure falls back to treating it as a Show."""
    url = "https://www.testsite.com/invalid/path"
    resource = Resource(
        url=url,
        source=url,
        last_updated=datetime.now(),
        metadata={"lastmod": datetime.now()}
    )
    result = fake_processor.process_resource(resource)
    # Since the URL doesn't match our episode pattern, it should be processed as a Show.
    assert isinstance(result, Show)
    assert result.description == "A description of the test show."
