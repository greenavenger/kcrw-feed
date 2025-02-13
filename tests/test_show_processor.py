"""Module to test the processing of shows"""

import pytest
from datetime import datetime

from kcrw_feed.show_processor import ShowProcessor
from kcrw_feed import utils
from kcrw_feed.models import Show, Episode

# Fake HTML for a Show page using microdata.
FAKE_SHOW_HTML = """
<html>
  <head>
    <title>Test Show Page</title>
  </head>
  <body itemscope itemtype="http://schema.org/RadioSeries">
    <span itemprop="name">Test Radio Show</span>
    <meta itemprop="identifier" content="show-uuid-123" />
    <meta itemprop="description" content="A description of the test show." />
  </body>
</html>
"""

# Fake HTML for an Episode page using microdata.
FAKE_EPISODE_HTML = """
<html>
  <head>
    <title>Test Episode Page</title>
  </head>
  <body itemscope itemtype="http://schema.org/NewsArticle">
    <span itemprop="name">Test Episode</span>
    <meta itemprop="identifier" content="episode-uuid-456" />
    <meta itemprop="description" content="A description of the test episode." />
    <link itemprop="contentUrl" href="https://www.testsite.com/audio/episode.mp3" />
    <meta itemprop="datePublished" content="2025-04-01T12:00:00" />
  </body>
</html>
"""


@pytest.fixture
def processor(monkeypatch):
    """Return a ShowProcessor instance with utils.get_file() monkeypatched to return
    predetermined HTML strings (as bytes) based on the URL."""
    sp = ShowProcessor(timeout=5)

    def fake_get_file(url: str, timeout: int = 10):
        if "episode" in url:
            return FAKE_EPISODE_HTML.encode("utf-8")
        return FAKE_SHOW_HTML.encode("utf-8")

    monkeypatch.setattr(utils, "get_file", fake_get_file)
    return sp


def test_fetch_show(processor):
    """
    Test that fetch() returns a Show object when the URL structure indicates a show.
    """
    url = "https://www.testsite.com/music/shows/test-show"
    result = processor.fetch(url)
    assert isinstance(result, Show)
    # Our fake microdata provides these values.
    assert result.title == "Test Radio Show"
    assert result.uuid == "show-uuid-123"
    assert "A description of the test show." in result.description


def test_fetch_episode(processor):
    """
    Test that fetch() returns an Episode object when the URL structure indicates an episode.
    """
    url = "https://www.testsite.com/music/shows/test-show/test-episode"
    result = processor.fetch(url)
    assert isinstance(result, Episode)
    assert result.title == "Test Episode"
    assert result.uuid == "episode-uuid-456"
    assert result.audio_url == "https://www.testsite.com/audio/episode.mp3"
    # Check that the publication date is parsed correctly.
    expected_date = datetime.fromisoformat("2025-04-01T12:00:00")
    assert result.airdate == expected_date


def test_fetch_invalid_structure_falls_back_to_show(processor):
    """
    Test that if the URL structure doesn't match the expected pattern,
    the processor falls back to treating it as a Show.
    """
    url = "https://www.testsite.com/invalid/path"
    result = processor.fetch(url)
    # Fallback should yield a Show object.
    assert isinstance(result, Show)
    # Since our fake HTML for shows is used, it will have the same microdata.
    assert result.title == "Test Radio Show"
