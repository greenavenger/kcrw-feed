"""Module to test the collection of shows"""

import pytest
from datetime import datetime
from typing import List
from kcrw_feed.models import Show, Episode
from kcrw_feed.show_index import ShowIndex


class FakeSitemapProcessor:
    """A fake SitemapProcessor that returns a fixed list of raw URLs."""

    def __init__(self, source_url: str, extra_sitemaps: List[str]):
        self.source_url = source_url
        self.extra_sitemaps = extra_sitemaps

    def gather_entries(self, source: str) -> List[str]:
        # Return a fixed list of URLs. Note: One URL does not match the music show regex.
        return [
            "https://www.testsite.com/music/shows/show1",
            "https://www.testsite.com/music/shows/show2",
            "https://www.testsite.com/music/shows/show3"
            # "https://www.testsite.com/other/url" # this would be filtered, so excluding
        ]


class FakeShowScraper:
    """A fake ShowScraper that returns a dummy Show object for a given URL."""

    def scrape_show(self, url: str) -> Show:
        # For testing, derive a dummy uuid and title from the URL.
        if "show1" in url:
            uuid = "uuid-show1"
            title = "Show One"
        elif "show2" in url:
            uuid = "uuid-show2"
            title = "Show Two"
        elif "show3" in url:
            uuid = "uuid-show3"
            title = "Show Three"
        else:
            uuid = None
            title = "Other"
        # Create a dummy Show. No episodes initially.
        return Show(
            title=title,
            url=url,
            uuid=uuid,
            description=f"Description for {title}",
            hosts=[],  # Empty list of hosts for simplicity.
            episodes=[],
            last_updated=datetime(2025, 1, 1),
            metadata={}
        )


@pytest.fixture
def fake_show_index():
    """Fixture that creates a ShowIndex with fake processor and scraper."""
    si = ShowIndex("https://www.testsite.com/",
                   extra_sitemaps=["extra-sitemap.xml"])
    # Replace the real processor with our fake one.
    si.sitemap_processor = FakeSitemapProcessor(
        si.source_url, si.extra_sitemaps)
    # Uncomment and assign our fake scraper.
    si.show_processor = FakeShowScraper()
    # Initialize the repository dictionary.
    si.shows = {}
    return si


def test_process_sitemap(fake_show_index):
    """Test that process_sitemap() returns the raw URLs from the fake processor."""
    raw_urls = fake_show_index.process_sitemap("sitemap")
    expected = [
        "https://www.testsite.com/music/shows/show1",
        "https://www.testsite.com/music/shows/show2",
        "https://www.testsite.com/music/shows/show3"
    ]
    assert set(raw_urls) == set(expected)


def test_update(fake_show_index):
    """
    Test that update() calls the scraper on the URLs and populates the shows
    dictionary with only music show URLs.
    """
    fake_show_index.update()
    # The fake processor returns 4 URLs, but filtering (using MUSIC_FILTER_RE in gather_entities)
    # should keep only the ones containing "/music/shows/".
    shows = fake_show_index.get_shows()
    # Expect 3 shows.
    assert len(shows) == 3
    # Verify lookup by UUID.
    show1 = fake_show_index.get_show_by_uuid("uuid-show1")
    show2 = fake_show_index.get_show_by_uuid("uuid-show2")
    show3 = fake_show_index.get_show_by_uuid("uuid-show3")
    assert show1 is not None and show1.title == "Show One"
    assert show2 is not None and show2.title == "Show Two"
    assert show3 is not None and show3.title == "Show Three"
    # The non-music URL should be filtered out.
    assert fake_show_index.get_show_by_name("Other") is None


def test_get_show_by_name(fake_show_index):
    """Test lookup by name (case-insensitive)."""
    fake_show_index.update()
    show = fake_show_index.get_show_by_name("show two")
    assert show is not None
    assert show.title == "Show Two"


def test_get_episodes(fake_show_index):
    """Test that get_episodes() returns a combined list of episodes from all shows."""
    # First update the index so that it has three shows.
    fake_show_index.update()
    # For one of the shows (say, show1), add an episode.
    show1 = fake_show_index.get_show_by_uuid("uuid-show1")
    ep = Episode(
        title="Episode 1",
        airdate=datetime(2025, 1, 2),
        audio_url="https://www.testsite.com/audio/1.mp3",
        uuid="ep1",
        description="Episode 1 description"
    )
    show1.episodes.append(ep)
    episodes = fake_show_index.get_episodes()
    assert len(episodes) == 1
    assert episodes[0].title == "Episode 1"


def test_get_episode_by_uuid(fake_show_index):
    """Test that get_episode_by_uuid() returns the correct episode."""
    fake_show_index.update()
    # Add an episode with a known UUID to show2.
    show2 = fake_show_index.get_show_by_uuid("uuid-show2")
    ep = Episode(
        title="Episode X",
        airdate=datetime(2025, 1, 3),
        audio_url="https://www.testsite.com/audio/x.mp3",
        uuid="ep-x",
        description="Test episode X"
    )
    show2.episodes.append(ep)
    found_ep = fake_show_index.get_episode_by_uuid("ep-x")
    assert found_ep is not None
    assert found_ep.title == "Episode X"
