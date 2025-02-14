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
    assert result.media_url == "https://www.testsite.com/audio/episode.mp3"
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


def test_deduplication_with_duplicates():
    dt = datetime.now()
    ep1 = Episode(title="Episode 1", airdate=dt, url="url1",
                  media_url="media1", uuid="uuid1")
    # Duplicate uuid; should be ignored in favor of the first occurrence.
    ep2 = Episode(title="Episode 2", airdate=dt, url="url2",
                  media_url="media2", uuid="uuid1")
    ep3 = Episode(title="Episode 3", airdate=dt, url="url3",
                  media_url="media3", uuid="uuid2")
    episodes = [ep1, ep2, ep3]

    deduped = dedup_by_uuid(episodes)
    assert len(deduped) == 2
    # Verify that the first instance of uuid "uuid1" is preserved
    assert deduped[0] == ep1
    # And that the episode with uuid "uuid2" is present.
    assert deduped[1] == ep3


def test_no_duplicates():
    dt = datetime.now()
    ep1 = Episode(title="Episode 1", airdate=dt, url="url1",
                  media_url="media1", uuid="uuid1")
    ep2 = Episode(title="Episode 2", airdate=dt, url="url2",
                  media_url="media2", uuid="uuid2")
    episodes = [ep1, ep2]

    deduped = dedup_by_uuid(episodes)
    # Both episodes have unique UUIDs so both should be present.
    assert len(deduped) == 2


def test_none_uuid():
    dt = datetime.now()
    # Episodes with no uuid should always be included.
    ep1 = Episode(title="Episode 1", airdate=dt,
                  url="url1", media_url="media1", uuid=None)
    ep2 = Episode(title="Episode 2", airdate=dt,
                  url="url2", media_url="media2", uuid=None)
    episodes = [ep1, ep2]

    deduped = dedup_by_uuid(episodes)
    assert len(deduped) == 2


def test_mix_of_none_and_duplicates():
    dt = datetime.now()
    ep1 = Episode(title="Episode 1", airdate=dt, url="url1",
                  media_url="media1", uuid="uuid1")
    ep2 = Episode(title="Episode 2", airdate=dt,
                  url="url2", media_url="media2", uuid=None)
    # Duplicate of uuid "uuid1" should be dropped.
    ep3 = Episode(title="Episode 3", airdate=dt, url="url3",
                  media_url="media3", uuid="uuid1")
    ep4 = Episode(title="Episode 4", airdate=dt, url="url4",
                  media_url="media4", uuid="uuid2")
    ep5 = Episode(title="Episode 5", airdate=dt,
                  url="url5", media_url="media5", uuid=None)
    episodes = [ep1, ep2, ep3, ep4, ep5]

    deduped = dedup_by_uuid(episodes)
    # Expecting:
    # ep1 (first instance of uuid "uuid1"),
    # ep2 (uuid is None, treated as unique),
    # ep4 (unique uuid "uuid2"),
    # ep5 (another None, also included)
    assert len(deduped) == 4
    assert deduped[0] == ep1
    assert deduped[1] == ep2
    assert deduped[2] == ep4
    assert deduped[3] == ep5
