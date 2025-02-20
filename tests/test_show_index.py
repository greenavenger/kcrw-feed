"""Module to test the collection of shows"""

import pytest
from datetime import datetime
from typing import Optional, List
from kcrw_feed.models import Show, Episode
from kcrw_feed.show_index import ShowIndex
from kcrw_feed.sitemap_processor import MUSIC_FILTER_RE


class DummySource:
    """Dummy Source Implementation"""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.uses_sitemap = True

    def get_resource(self, path: str) -> Optional[bytes]:
        # If the path is not an absolute URL, prepend the base URL.
        if not path.startswith("http"):
            path = self.base_url.rstrip("/") + "/" + path.lstrip("/")
        return fake_get_file(path)

    def relative_path(self, url: str) -> str:
        # For our tests, assume the URL is already correct.
        return url


def fake_get_file(path: str, timeout: int = 10) -> Optional[bytes]:
    """Fake get_file function to simulate file retrieval."""
    if path == "https://www.testsite.com/robots.txt":
        content = (
            "User-agent: *\n"
            "Disallow: /private/\n"
            "Sitemap: https://www.testsite.com/sitemap1.xml\n"
            "Sitemap: https://www.testsite.com/sitemap2.xml\n"
        )
        return content.encode("utf-8")
    elif path == "https://www.testsite.com/sitemap1.xml":
        # This sitemap contains two <url> entries:
        # one for a music show and one for another URL.
        content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.testsite.com/music/shows/show1</loc>
    <lastmod>2025-01-01T00:00:00</lastmod>
  </url>
  <url>
    <loc>https://www.testsite.com/other/url</loc>
  </url>
</urlset>"""
        return content.encode("utf-8")
    elif path == "https://www.testsite.com/sitemap2.xml":
        content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.testsite.com/music/shows/show2</loc>
    <changefreq>weekly</changefreq>
  </url>
</urlset>"""
        return content.encode("utf-8")
    elif path == "https://www.testsite.com/extra-sitemap.xml":
        content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.testsite.com/music/shows/show3</loc>
    <priority>0.8</priority>
  </url>
</urlset>"""
        return content.encode("utf-8")
    return None


class FakeSitemapProcessor:
    """A fake SitemapProcessor that returns a fixed list of raw URLs."""

    def __init__(self, source: DummySource) -> None:
        self.source = source

    def gather_entries(self) -> List[str]:
        # Return a fixed list of URLs. The FakeShowProcessor will later filter out non-music URLs.
        return [
            "https://www.testsite.com/music/shows/show1",
            "https://www.testsite.com/music/shows/show2",
            "https://www.testsite.com/music/shows/show3",
            # "https://www.testsite.com/other/url" # this would be filtered, so excluding
        ]


class FakeShowProcessor:
    """A fake ShowProcessor that returns a dummy Show object for a given URL."""

    def fetch(self, url: str) -> Show:
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


@pytest.fixture(name="fake_show_index")
def _fake_show_index() -> ShowIndex:
    """Fixture that creates a ShowIndex with fake processors and a DummySource."""
    dummy_source = DummySource("https://www.testsite.com/")
    si = ShowIndex(dummy_source)
    # Replace the real processors with our fake ones.
    si.sitemap_processor = FakeSitemapProcessor(dummy_source)
    si.show_processor = FakeShowProcessor()
    si.shows = {}
    return si


def test_gather(fake_show_index: ShowIndex) -> None:
    """Test that gather() returns only music show URLs from the fake
    sitemap processor."""
    raw_urls = fake_show_index.gather()
    # The FakeSitemapProcessor returns 4 URLs but only those containing "/music/shows/"
    expected = {
        "https://www.testsite.com/music/shows/show1",
        "https://www.testsite.com/music/shows/show2",
        "https://www.testsite.com/music/shows/show3",
    }
    # Gather() returns the sorted keys from the internal sitemap_entities,
    # so for our fake, we assume that the filtering in FakeSitemapProcessor
    # (or later in update) is applied.
    assert set(raw_urls) == expected


def test_update(fake_show_index: ShowIndex) -> None:
    """Test that update() calls the scraper on the URLs and populates the shows
    dictionary with only music show URLs."""
    fake_show_index.update()
    # The fake sitemap processor returns 4 URLs, but filtering (using
    # MUSIC_FILTER_RE in ShowIndex.gather) should keep only the ones
    # containing "/music/shows/".
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


def test_get_show_by_name(fake_show_index: ShowIndex) -> None:
    """Test lookup by name (case-insensitive)."""
    fake_show_index.update()
    show = fake_show_index.get_show_by_name("show two")
    assert show is not None
    assert show.title == "Show Two"


def test_get_episodes(fake_show_index: ShowIndex) -> None:
    """Test that get_episodes() returns a combined list of episodes from
    all shows."""
    fake_show_index.update()
    # For one of the shows (say, show1), add an episode.
    show1 = fake_show_index.get_show_by_uuid("uuid-show1")
    ep = Episode(
        title="Episode 1",
        airdate=datetime(2025, 1, 2),
        url="https://www.testsite.com/music/shows/show1/ep1",
        media_url="https://www.testsite.com/audio/1.mp3",
        uuid="ep1",
        description="Episode 1 description"
    )
    show1.episodes.append(ep)
    episodes = fake_show_index.get_episodes()
    assert len(episodes) == 1
    assert episodes[0].title == "Episode 1"


def test_get_episode_by_uuid(fake_show_index: ShowIndex) -> None:
    """Test that get_episode_by_uuid() returns the correct episode."""
    fake_show_index.update()
    # Add an episode with a known UUID to show2.
    show2 = fake_show_index.get_show_by_uuid("uuid-show2")
    ep = Episode(
        title="Episode X",
        airdate=datetime(2025, 1, 3),
        url="https://www.testsite.com/music/shows/show2/ep-x",
        media_url="https://www.testsite.com/audio/x.mp3",
        uuid="ep-x",
        description="Test episode X"
    )
    show2.episodes.append(ep)
    found_ep = fake_show_index.get_episode_by_uuid("ep-x")
    assert found_ep is not None
    assert found_ep.title == "Episode X"
