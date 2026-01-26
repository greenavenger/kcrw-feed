"""Module to test the processing of Shows."""

import pytest
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from kcrw_feed.models import Show, Episode, Resource
from kcrw_feed.processing.station import StationProcessor

# Fake HTML for a Show page (new format with meta tags)
FAKE_SHOW_HTML = """
<!DOCTYPE html>
<html>
  <head>
    <title>Test Radio Show | KCRW</title>
    <meta property="og:title" content="Test Radio Show | KCRW" />
    <meta property="og:description" content="A description of the test show." />
    <meta property="og:url" content="https://www.testsite.com/shows/test-show" />
    <meta property="og:image" content="https://www.testsite.com/image.jpg" />
  </head>
  <body>
    <h1>Test Radio Show</h1>
  </body>
</html>
"""

# Fake HTML for an Episode page (new format with meta tags and audio URL)
FAKE_EPISODE_HTML = """
<!DOCTYPE html>
<html>
  <head>
    <title>Test Episode | KCRW</title>
    <meta property="og:title" content="Test Episode | KCRW" />
    <meta property="og:description" content="A description of the test episode." />
    <meta property="og:url" content="https://www.testsite.com/shows/test-show/stories/test-episode" />
    <meta property="og:image" content="https://www.testsite.com/image.jpg" />
    <meta property="article:published_time" content="2025-04-01T12:00:00" />
  </head>
  <body>
    <audio src="https://www.testsite.com/audio/episode.mp3"></audio>
  </body>
</html>
"""

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
        self.shows[str(show.uuid)] = show

    def list_episodes(self) -> List[Episode]:
        return list(self.episodes.values())

    def add_episode(self, episode: Episode) -> None:
        key = str(episode.uuid) if episode.uuid is not None else episode.url
        self.episodes[key] = episode

    def get_resource(self, url: str) -> Optional[Resource]:
        return self.resources.get(url)


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
    # If URL indicates an episode page.
    if "stories" in url and "test-episode" in url:
        return FAKE_EPISODE_HTML.encode("utf-8")
    # If URL indicates a show page.
    if "test-show" in url:
        return FAKE_SHOW_HTML.encode("utf-8")
    return FAKE_SHOW_HTML.encode("utf-8")


@pytest.fixture(name="fake_processor")
def fake_processor_fixture(monkeypatch: pytest.MonkeyPatch) -> StationProcessor:
    """Create a StationProcessor using a FakeCatalog."""
    fake_catalog = FakeCatalog()
    dummy_source = DummySource("https://www.testsite.com/")
    monkeypatch.setattr(dummy_source, 'get_reference', fake_get_file)
    fake_catalog.source = dummy_source

    from kcrw_feed.processing import station
    sp = station.StationProcessor(fake_catalog)
    return sp


def test_process_show(fake_processor: StationProcessor):
    """Test that process_resource() returns a Show object when given a
    show URL."""
    url = "https://www.testsite.com/shows/test-show"
    resource = Resource(
        url=url,
        source=url,
        last_updated=datetime.now(),
        metadata={"lastmod": datetime.now()}
    )
    result = fake_processor.process_resource(resource)
    assert result is not None
    assert isinstance(result, Show)
    assert result.title == "Test Radio Show"
    # UUID should be deterministically generated from URL
    expected_uuid = uuid.uuid5(uuid.NAMESPACE_URL, url)
    assert result.uuid == expected_uuid
    assert result.description == "A description of the test show."


def test_process_episode(fake_processor: StationProcessor):
    """Test that process_resource() returns an Episode object when given
    an episode URL."""
    url = "https://www.testsite.com/shows/test-show/stories/test-episode"
    resource = Resource(
        url=url,
        source=url,
        last_updated=datetime.now(),
        metadata={"lastmod": datetime.now()}
    )
    result = fake_processor.process_resource(resource)
    assert isinstance(result, Episode)
    assert result.title == "Test Episode"
    # UUID should be deterministically generated from URL
    expected_uuid = uuid.uuid5(uuid.NAMESPACE_URL, url)
    assert result.uuid == expected_uuid
    # Check that show_uuid is derived from the show URL
    show_url = "https://www.testsite.com/shows/test-show"
    expected_show_uuid = uuid.uuid5(uuid.NAMESPACE_URL, show_url)
    assert result.show_uuid == expected_show_uuid
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
