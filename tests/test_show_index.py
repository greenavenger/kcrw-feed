"""Module to test the collection of shows"""

from datetime import datetime, timezone
from pathlib import Path
import pytest
import uuid
from typing import Any, Dict, List, Optional
from kcrw_feed.models import Show, Episode, Resource
from kcrw_feed.show_index import ShowIndex
from kcrw_feed.processing.resources import MUSIC_FILTER_RE

UUID_EP1 = uuid.uuid4()
UUID_EP2 = uuid.uuid4()
UUID_SHOW1 = uuid.uuid4()
UUID_SHOW2 = uuid.uuid4()
UUID_SHOW3 = uuid.uuid4()


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
    """A fake SitemapProcessor that returns a fixed dict of raw URLs
    with metadata."""

    def __init__(self, source: DummySource) -> None:
        self.source = source

    def fetch_resources(self) -> Dict[str, Any]:
        # Return a fixed dict of resource URLs with some metadata.
        now = datetime.now()
        return {
            "https://www.testsite.com/music/shows/show1": {"lastmod": now},
            "https://www.testsite.com/music/shows/show2": {"lastmod": now},
            "https://www.testsite.com/music/shows/show3": {"lastmod": now},
            # "https://www.testsite.com/other/url": {"lastmod": now} # this would be filtered, so excluding
        }


class FakeShowProcessor:
    """A fake ShowProcessor that returns a dummy Show object for a given URL."""

    def fetch(self, url: str, resource: Optional[Resource] = None) -> Show:
        # For testing, derive a dummy uuid and title from the URL.
        if "show1" in url:
            uid = UUID_SHOW1
            title = "Show One"
        elif "show2" in url:
            uid = UUID_SHOW2
            title = "Show Two"
        elif "show3" in url:
            uid = UUID_SHOW3
            title = "Show Three"
        else:
            uid = None
            title = "Other"
        # Create a dummy Show. No episodes initially.
        return Show(
            title=title,
            url=url,
            uuid=uid,
            description=f"Description for {title}",
            hosts=[],  # Empty list of hosts for simplicity.
            episodes=[],  # Initially empty.
            last_updated=datetime(2025, 1, 1, tzinfo=timezone.utc),
            resource=resource,
            metadata={}
        )

    def is_show_resource(self, resource: str) -> bool:
        # For testing, if "episode" is in the URL, then it's not a show.
        if "episode" in resource:
            return False
        return True

    def is_episode_resouce(self, resource: str) -> bool:
        return not self.is_show_resource(resource)

    def get_episodes(self) -> List[Episode]:
        return []

    def get_shows(self) -> List[Show]:
        """Return a list of dummy Show objects based on fixed URLs."""
        return [
            self.fetch("https://www.testsite.com/music/shows/show1"),
            self.fetch("https://www.testsite.com/music/shows/show2"),
            self.fetch("https://www.testsite.com/music/shows/show3"),
        ]


@pytest.fixture(name="fake_show_index")
def _fake_show_index(tmp_path: Path) -> ShowIndex:
    """Fixture that creates a ShowIndex with fake processors and a DummySource,
    using a temporary directory for storage."""
    dummy_source = DummySource("https://www.testsite.com/")
    # Use tmp_path (a Path object) for a temporary storage root.
    storage_root = str(tmp_path / "state")
    state_file = "test_kcrw_feed.json"
    feed_directory = "feeds"
    # Ensure the directory exists.
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    si = ShowIndex(dummy_source, storage_root, state_file, feed_directory)
    # Replace the real processors with our fake ones.
    si.resource_processor = FakeSitemapProcessor(dummy_source)
    si.station_processor = FakeShowProcessor()
    si._entities = {}
    return si


def test_gather(fake_show_index: ShowIndex) -> None:
    """Test that gather() returns the expected dict of resources."""
    entries = fake_show_index.gather()
    expected = {
        "https://www.testsite.com/music/shows/show1",
        "https://www.testsite.com/music/shows/show2",
        "https://www.testsite.com/music/shows/show3",
    }
    assert set(entries.keys()) == expected


def test_update(fake_show_index: ShowIndex) -> None:
    """Test that update() populates _entities with enriched shows."""
    count = fake_show_index.update()
    # Expect 3 shows.
    assert count == 3
    shows = fake_show_index.get_shows()
    print("shows:", shows)
    assert len(shows) == 3
    show1 = fake_show_index.get_show_by_uuid(UUID_SHOW1)
    show2 = fake_show_index.get_show_by_uuid(UUID_SHOW2)
    show3 = fake_show_index.get_show_by_uuid(UUID_SHOW3)
    assert show1 is not None and show1.title == "Show One"
    assert show2 is not None and show2.title == "Show Two"
    assert show3 is not None and show3.title == "Show Three"
    # The non-music URL is not present in our fake data, so get_show_by_name("Other") should be None.
    assert fake_show_index.get_show_by_name("Other") is None


def test_get_show_by_name(fake_show_index: ShowIndex) -> None:
    """Test lookup by name (case-insensitive)."""
    fake_show_index.update()
    show = fake_show_index.get_show_by_name("show two")
    assert show is not None
    assert show.title == "Show Two"


def test_get_episodes(fake_show_index: ShowIndex) -> None:
    """Test that get_episodes() returns a combined list of episodes from all shows."""
    fake_show_index.update()
    # For show1, add an episode.
    show1 = fake_show_index.get_show_by_uuid(UUID_SHOW1)
    # Make sure show1 exists.
    assert show1 is not None
    # Initialize its episodes list if not already.
    if show1.episodes is None:
        show1.episodes = []
    ep = Episode(
        title="Episode 1",
        airdate=datetime(2025, 1, 2, tzinfo=timezone.utc),
        url="https://www.testsite.com/music/shows/show1/ep1",
        media_url="https://www.testsite.com/audio/1.mp3",
        uuid=UUID_EP1,
        description="Episode 1 description"
    )
    show1.episodes.append(ep)
    episodes = fake_show_index.get_episodes()
    # Since our fake update() only created shows (with empty episode lists) and we added one episode,
    # get_episodes() should return that one episode.
    assert len(episodes) == 1
    assert episodes[0].title == "Episode 1"


def test_get_episode_by_uuid(fake_show_index: ShowIndex) -> None:
    """Test that get_episode_by_uuid() returns the correct episode."""
    fake_show_index.update()
    # For show2, add an episode.
    show2 = fake_show_index.get_show_by_uuid(UUID_SHOW2)
    assert show2 is not None
    if show2.episodes is None:
        show2.episodes = []
    ep = Episode(
        title="Episode X",
        airdate=datetime(2025, 1, 3, tzinfo=timezone.utc),
        url="https://www.testsite.com/music/shows/show2/ep-x",
        media_url="https://www.testsite.com/audio/x.mp3",
        uuid=UUID_EP2,
        description="Test episode X"
    )
    show2.episodes.append(ep)
    found_ep = fake_show_index.get_episode_by_uuid(UUID_EP2)
    assert found_ep is not None
    assert found_ep.title == "Episode X"
