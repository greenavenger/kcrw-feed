"""Tests for the station_catalog module."""

import json
import os
# import tempfile
import uuid
from datetime import datetime
# from pathlib import Path
from typing import Dict, List, Any
import pytest

from kcrw_feed.models import Show, Episode, Host, Resource, ShowDirectory, Catalog
from kcrw_feed.station_catalog import BaseStationCatalog, LocalStationCatalog, LiveStationCatalog, STATE_CATALOG_FILE
from kcrw_feed.source_manager import BaseSource, CacheSource
from kcrw_feed.persistence.feeds import FeedPersister
from kcrw_feed.persistence.state import StatePersister

GOLDEN_FILES_DIR = "tests/data"
DIRECTORY_FILE = "kcrw_feed.json"
CATALOG_FILE = "kcrw_catalog.json"

# Minimal test config
TEST_CONFIG: Dict[str, Any] = {
    "source_root": "https://www.example.com/",
    "storage_root": ".",
    "state_file": CATALOG_FILE,
    "feed_directory": "catalog/feeds",
    "http_timeout": 25,
    "request_delay": {
        "mean": 5.0,
        "stddev": 2.0
    },
    "request_headers": {
        "User-Agent": "Test User Agent"
    }
}


class MockSource(BaseSource):
    """Mock source for testing."""

    def __init__(self, resources=None):
        self.resources = resources or []
        self.robots_txt_content = "User-agent: *\nAllow: /"

    def get_reference(self, resource: str) -> bytes | None:
        return super().get_reference(resource)

    def reference(self, entity_reference: str) -> str:
        return super().reference(entity_reference)

    def relative_path(self, entity_reference: str) -> str:
        return super().relative_path(entity_reference)

    def fetch_resources(self) -> Dict[str, Resource]:
        """Return the mock resources."""
        return {r.url: r for r in self.resources}

    def get_robots_txt(self):
        """Return mock robots.txt content."""
        return self.robots_txt_content


class MockFeedPersister(FeedPersister):
    """Mock feed persister for testing."""

    def __init__(self):
        self.saved_shows = []

    def save(self, show_directory: ShowDirectory, feed_directory: str = None) -> None:
        """Record the shows that would be saved."""
        self.saved_shows = show_directory.shows


class MockStatePersister(StatePersister):
    """Mock state persister for testing."""

    def __init__(self, storage_root: str, state_file: str):
        super().__init__(storage_root, state_file)
        self.saved_states = []
        self.saved_filenames = []

    def save(self, state: ShowDirectory | Catalog, filename: str = None) -> None:
        """Record the state that would be saved."""
        self.saved_states.append(state)
        self.saved_filenames.append(filename or self.filename)

    def load(self, filename: str = None) -> ShowDirectory | Catalog:
        """Return a mock catalog for testing."""
        # Create a simple catalog with one show, one episode, and one host
        host = Host(
            name="Test Host",
            uuid=uuid.uuid4(),
            title="Test Title",
            url="https://example.com/host",
            image="https://example.com/host.jpg",
            description="Test host description"
        )

        resource = Resource(
            url="https://example.com/resource",
            source="test",
            last_updated=datetime.now(),
            metadata={"lastmod": datetime.now()}
        )

        episode = Episode(
            title="Test Episode",
            airdate=datetime.now(),
            url="https://example.com/episode",
            media_url="https://example.com/episode.mp3",
            uuid=uuid.uuid4(),
            hosts=[host],
            description="Test episode description",
            resource=resource
        )

        show = Show(
            title="Test Show",
            url="https://example.com/show",
            image="https://example.com/show.jpg",
            uuid=uuid.uuid4(),
            description="Test show description",
            hosts=[host],
            episodes=[episode],
            last_updated=datetime.now(),
            resource=resource
        )

        # Check if this is a catalog request or a show directory request
        if filename and filename.endswith(STATE_CATALOG_FILE):
            catalog = Catalog()
            catalog.shows[show.uuid] = show
            catalog.episodes[episode.uuid] = episode
            catalog.hosts[host.uuid] = host
            catalog.resources[resource.url] = resource
            return catalog
        else:
            return ShowDirectory(shows=[show])


@pytest.fixture
def mock_resource():
    """Create a mock resource for testing."""
    return Resource(
        url="https://example.com/resource",
        source="test",
        last_updated=datetime.now(),
        metadata={"lastmod": datetime.now()}
    )


@pytest.fixture
def mock_host():
    """Create a mock host for testing."""
    return Host(
        name="Test Host",
        uuid=uuid.uuid4(),
        title="Test Title",
        url="https://example.com/host",
        image="https://example.com/host.jpg",
        description="Test host description"
    )


@pytest.fixture
def mock_episode(mock_host, mock_resource):
    """Create a mock episode for testing."""
    return Episode(
        title="Test Episode",
        airdate=datetime.now(),
        url="https://example.com/episode",
        media_url="https://example.com/episode.mp3",
        uuid=uuid.uuid4(),
        hosts=[mock_host],
        description="Test episode description",
        resource=mock_resource
    )


@pytest.fixture
def mock_show(mock_host, mock_episode, mock_resource):
    """Create a mock show for testing."""
    return Show(
        title="Test Show",
        url="https://example.com/show",
        image="https://example.com/show.jpg",
        uuid=uuid.uuid4(),
        description="Test show description",
        hosts=[mock_host],
        episodes=[mock_episode],
        last_updated=datetime.now(),
        resource=mock_resource
    )


@pytest.fixture
def mock_catalog(mock_show, mock_episode, mock_host, mock_resource):
    """Create a mock catalog for testing."""
    catalog = Catalog()
    catalog.shows[mock_show.uuid] = mock_show
    catalog.episodes[mock_episode.uuid] = mock_episode
    catalog.hosts[mock_host.uuid] = mock_host
    catalog.resources[mock_resource.url] = mock_resource
    return catalog


class TestBaseStationCatalog:
    """Tests for the BaseStationCatalog class."""

    def test_list_resources(self, mock_catalog):
        """Test listing resources."""
        # Create a concrete implementation of the abstract class
        class ConcreteCatalog(BaseStationCatalog):
            def load(self) -> Catalog:
                return mock_catalog

        catalog = ConcreteCatalog()
        catalog.catalog = mock_catalog

        resources = catalog.list_resources()
        assert len(resources) == 1
        assert resources[0].url == "https://example.com/resource"

    def test_list_shows(self, mock_catalog):
        """Test listing shows."""
        # Create a concrete implementation of the abstract class
        class ConcreteCatalog(BaseStationCatalog):
            def load(self) -> Catalog:
                return mock_catalog

        catalog = ConcreteCatalog()
        catalog.catalog = mock_catalog

        shows = catalog.list_shows()
        assert len(shows) == 1
        assert shows[0].title == "Test Show"

    def test_list_episodes(self, mock_catalog):
        """Test listing episodes."""
        # Create a concrete implementation of the abstract class
        class ConcreteCatalog(BaseStationCatalog):
            def load(self) -> Catalog:
                return mock_catalog

        catalog = ConcreteCatalog()
        catalog.catalog = mock_catalog

        episodes = catalog.list_episodes()
        assert len(episodes) == 1
        assert episodes[0].title == "Test Episode"

    def test_list_hosts(self, mock_catalog):
        """Test listing hosts."""
        # Create a concrete implementation of the abstract class
        class ConcreteCatalog(BaseStationCatalog):
            def load(self) -> Catalog:
                return mock_catalog

        catalog = ConcreteCatalog()
        catalog.catalog = mock_catalog

        hosts = catalog.list_hosts()
        assert len(hosts) == 1
        assert hosts[0].name == "Test Host"

    def test_has_show(self, mock_catalog, mock_show):
        """Test checking if a show exists."""
        # Create a concrete implementation of the abstract class
        class ConcreteCatalog(BaseStationCatalog):
            def load(self) -> Catalog:
                return mock_catalog

        catalog = ConcreteCatalog()
        catalog.catalog = mock_catalog

        assert catalog.has_show(mock_show.uuid) is True
        assert catalog.has_show(uuid.uuid4()) is False

    def test_has_episode(self, mock_catalog, mock_episode):
        """Test checking if an episode exists."""
        # Create a concrete implementation of the abstract class
        class ConcreteCatalog(BaseStationCatalog):
            def load(self) -> Catalog:
                return mock_catalog

        catalog = ConcreteCatalog()
        catalog.catalog = mock_catalog

        assert catalog.has_episode(mock_episode.uuid) is True
        assert catalog.has_episode(uuid.uuid4()) is False

    def test_get_resource(self, mock_catalog, mock_resource):
        """Test getting a resource by URL."""
        # Create a concrete implementation of the abstract class
        class ConcreteCatalog(BaseStationCatalog):
            def load(self) -> Catalog:
                return mock_catalog

        catalog = ConcreteCatalog()
        catalog.catalog = mock_catalog

        resource = catalog.get_resource(mock_resource.url)
        assert resource is not None
        assert resource.url == mock_resource.url

        resource = catalog.get_resource("https://example.com/nonexistent")
        assert resource is None

    def test_get_show(self, mock_catalog, mock_show):
        """Test getting a show by UUID."""
        # Create a concrete implementation of the abstract class
        class ConcreteCatalog(BaseStationCatalog):
            def load(self) -> Catalog:
                return mock_catalog

        catalog = ConcreteCatalog()
        catalog.catalog = mock_catalog

        show = catalog.get_show(mock_show.uuid)
        assert show is not None
        assert show.title == mock_show.title

        show = catalog.get_show(uuid.uuid4())
        assert show is None

    def test_add_resource(self, mock_catalog, mock_resource):
        """Test adding a resource."""
        # Create a concrete implementation of the abstract class
        class ConcreteCatalog(BaseStationCatalog):
            def load(self) -> Catalog:
                return mock_catalog

        catalog = ConcreteCatalog()
        catalog.catalog = mock_catalog

        # Create a new resource
        new_resource = Resource(
            url="https://example.com/new-resource",
            source="test",
            last_updated=datetime.now(),
            metadata={"lastmod": datetime.now()}
        )

        # Add the resource
        catalog.add_resource(new_resource)

        # Check that the resource was added
        assert new_resource.url in catalog.catalog.resources
        assert catalog.catalog.resources[new_resource.url] == new_resource

    def test_add_show(self, mock_catalog, mock_show):
        """Test adding a show."""
        # Create a concrete implementation of the abstract class
        class ConcreteCatalog(BaseStationCatalog):
            def load(self) -> Catalog:
                return mock_catalog

        catalog = ConcreteCatalog()
        catalog.catalog = mock_catalog

        # Create a new show
        new_show = Show(
            title="New Show",
            url="https://example.com/new-show",
            image="https://example.com/new-show.jpg",
            uuid=uuid.uuid4(),
            description="New show description",
            hosts=[],
            episodes=[],
            last_updated=datetime.now(),
            resource=None
        )

        # Add the show
        catalog.add_show(new_show)

        # Check that the show was added
        assert new_show.uuid in catalog.catalog.shows
        assert catalog.catalog.shows[new_show.uuid] == new_show

    def test_add_episode(self, mock_catalog, mock_episode):
        """Test adding an episode."""
        # Create a concrete implementation of the abstract class
        class ConcreteCatalog(BaseStationCatalog):
            def load(self) -> Catalog:
                return mock_catalog

        catalog = ConcreteCatalog()
        catalog.catalog = mock_catalog

        # Create a new episode
        new_episode = Episode(
            title="New Episode",
            airdate=datetime.now(),
            url="https://example.com/new-episode",
            media_url="https://example.com/new-episode.mp3",
            uuid=uuid.uuid4(),
            hosts=[],
            description="New episode description",
            resource=None
        )

        # Add the episode
        catalog.add_episode(new_episode)

        # Check that the episode was added
        assert new_episode.uuid in catalog.catalog.episodes
        assert catalog.catalog.episodes[new_episode.uuid] == new_episode

    def test_add_host(self, mock_catalog, mock_host):
        """Test adding a host."""
        # Create a concrete implementation of the abstract class
        class ConcreteCatalog(BaseStationCatalog):
            def load(self) -> Catalog:
                return mock_catalog

        catalog = ConcreteCatalog()
        catalog.catalog = mock_catalog

        # Create a new host
        new_host = Host(
            name="New Host",
            uuid=uuid.uuid4(),
            title="New Title",
            url="https://example.com/new-host",
            image="https://example.com/new-host.jpg",
            description="New host description"
        )

        # Add the host
        catalog.add_host(new_host)

        # Check that the host was added
        assert new_host.uuid in catalog.catalog.hosts
        assert catalog.catalog.hosts[new_host.uuid] == new_host

    def test_diff(self, mock_catalog):
        """Test diffing two catalogs."""
        # Create two concrete implementations of the abstract class
        class ConcreteCatalog(BaseStationCatalog):
            def load(self) -> Catalog:
                return mock_catalog

        catalog1 = ConcreteCatalog()
        catalog1.catalog = mock_catalog

        # Create a second catalog with some differences
        catalog2 = ConcreteCatalog()
        catalog2.catalog = Catalog()

        # Add a new resource to catalog2
        new_resource = Resource(
            url="https://example.com/new-resource",
            source="test",
            last_updated=datetime.now(),
            metadata={"lastmod": datetime.now()}
        )
        catalog2.catalog.resources[new_resource.url] = new_resource

        # Modify an existing resource in catalog2
        modified_resource = Resource(
            url="https://example.com/resource",
            source="test-modified",
            last_updated=datetime.now(),
            metadata={"lastmod": datetime.now(), "new_field": "new_value"}
        )
        catalog2.catalog.resources[modified_resource.url] = modified_resource

        # Diff the catalogs
        diff = catalog1.diff(catalog2)

        # Check the diff results
        assert len(diff.added) == 1
        assert diff.added[0].url == "https://example.com/new-resource"

        assert len(diff.removed) == 0

        assert len(diff.modified) == 1
        assert diff.modified[0].current.url == "https://example.com/resource"
        assert diff.modified[0].new.url == "https://example.com/resource"

        # Check that the new field was added in the metadata
        assert "dictionary_item_added" in diff.modified[0].diff
        assert any(
            "new_field" in path for path in diff.modified[0].diff["dictionary_item_added"])

        # Check that the source was modified
        assert "values_changed" in diff.modified[0].diff
        assert "root['source']" in diff.modified[0].diff["values_changed"]
        assert diff.modified[0].diff["values_changed"]["root['source']"]["new_value"] == "test-modified"


class TestLocalStationCatalog:
    """Tests for the LocalStationCatalog class."""

    def test_init(self, tmp_path):
        """Test initialization."""
        # Create a temporary directory for testing
        storage_root = str(tmp_path)
        state_file = "test_state.json"

        # Create a mock feed persister
        feed_persister = MockFeedPersister()

        # Create a CacheSource for local storage
        local_source = CacheSource(storage_root, TEST_CONFIG)

        # Create a LocalStationCatalog
        catalog = LocalStationCatalog(
            catalog_source=local_source,
            state_file=state_file,
            feed_persister=feed_persister
        )

        assert catalog.catalog_source == local_source
        assert catalog.state_file == state_file
        assert catalog.feed_persister == feed_persister

    def test_save_state(self, tmp_path):
        """Test saving state."""
        # Create a temporary directory for testing
        storage_root = str(tmp_path)
        state_file = "test_state.json"

        # Create a mock feed persister
        feed_persister = MockFeedPersister()

        # Create a CacheSource for local storage
        local_source = CacheSource(storage_root, TEST_CONFIG)

        # Create a LocalStationCatalog
        catalog = LocalStationCatalog(
            catalog_source=local_source,
            state_file=state_file,
            feed_persister=feed_persister
        )

        # Mock the state persister
        catalog.state_persister = MockStatePersister(storage_root, state_file)

        # Save the state
        catalog.save_state()

        # Check that the state was saved correctly
        assert len(catalog.state_persister.saved_states) == 2
        assert isinstance(
            catalog.state_persister.saved_states[0], ShowDirectory)
        assert isinstance(catalog.state_persister.saved_states[1], Catalog)


def test_load_from_golden_files():
    """Test loading a catalog from golden files in tests/data directory."""
    # Create a CacheSource for the golden files directory
    local_source = CacheSource(GOLDEN_FILES_DIR, TEST_CONFIG)

    # Create a local catalog pointing to the tests/data directory
    catalog = LocalStationCatalog(
        catalog_source=local_source,
        state_file=CATALOG_FILE,
        feed_persister=None
    )

    # Load the catalog from the golden files
    loaded_catalog = catalog.load()

    # Check that the catalog was loaded correctly
    assert loaded_catalog is not None

    # Check that shows were loaded
    assert len(loaded_catalog.shows) > 0
    # Sample a few shows and check their properties
    for show_uuid, show in list(loaded_catalog.shows.items())[:3]:
        assert show.title is not None
        assert show.url is not None
        assert show.uuid is not None

    # Check that episodes were loaded
    assert len(loaded_catalog.episodes) > 0
    # Sample a few episodes and check their properties
    for episode_uuid, episode in list(loaded_catalog.episodes.items())[:3]:
        assert episode.title is not None
        assert episode.url is not None
        assert episode.uuid is not None
        assert episode.airdate is not None

    # Check that hosts were loaded
    assert len(loaded_catalog.hosts) > 0
    # Sample a few hosts and check their properties
    for host_uuid, host in list(loaded_catalog.hosts.items())[:3]:
        assert host.name is not None
        assert host.url is not None
        assert host.uuid is not None

    # Check that resources were loaded
    assert len(loaded_catalog.resources) > 0
    # Sample a few resources and check their properties
    for resource_url, resource in list(loaded_catalog.resources.items())[:3]:
        assert resource.url is not None
        assert resource.source is not None
        assert resource.last_updated is not None


def test_compare_directory_and_catalog_files(tmp_path):
    """Test comparing kcrw_feed.json and kcrw_catalog.json to ensure they're consistent."""
    # Create temporary files for testing
    directory_file = tmp_path / DIRECTORY_FILE
    catalog_file = tmp_path / CATALOG_FILE

    # Create a mock show directory
    show = Show(
        title="Test Show",
        url="https://example.com/show",
        image="https://example.com/show.jpg",
        uuid=uuid.uuid4(),
        description="Test show description",
        hosts=[],
        episodes=[],
        last_updated=datetime.now(),
        resource=None
    )

    show_directory = ShowDirectory(shows=[show])

    # Create a mock catalog
    catalog = Catalog()
    catalog.shows[show.uuid] = show

    # Create a state persister
    state_persister = StatePersister(str(tmp_path), "test_state.json")

    # Save the show directory and catalog
    state_persister.save(show_directory, str(directory_file))
    state_persister.save(catalog, str(catalog_file))

    # Load the files
    with open(directory_file, "r") as f:
        directory_data = json.load(f)

    with open(catalog_file, "r") as f:
        catalog_data = json.load(f)

    # Check that the files are consistent
    assert directory_data["shows"][0]["uuid"] == catalog_data["shows"][str(
        show.uuid)]["uuid"]
    assert directory_data["shows"][0]["title"] == catalog_data["shows"][str(
        show.uuid)]["title"]
    assert directory_data["shows"][0]["url"] == catalog_data["shows"][str(
        show.uuid)]["url"]


def test_compare_real_directory_and_catalog_files():
    """Test comparing real kcrw_feed.json and kcrw_catalog.json files."""
    # Skip this test if the files don't exist
    golden_directory_file = os.path.join(GOLDEN_FILES_DIR, DIRECTORY_FILE)
    golden_catalog_file = os.path.join(GOLDEN_FILES_DIR, CATALOG_FILE)
    if not os.path.exists(golden_directory_file) or not os.path.exists(golden_catalog_file):
        pytest.skip("kcrw_feed.json or kcrw_catalog.json not found")

    # Load the files
    with open(golden_directory_file, "r") as f:
        directory_data = json.load(f)

    with open(golden_catalog_file, "r") as f:
        catalog_data = json.load(f)

    # Check that the files have the expected structure
    assert "shows" in directory_data
    assert "type" in catalog_data
    assert catalog_data["type"] == "catalog"
    assert "shows" in catalog_data

    # Check that the shows in both files are consistent
    directory_shows = {show["uuid"]: show for show in directory_data["shows"]}
    catalog_shows = catalog_data["shows"]

    # Check that all shows in the directory are in the catalog
    for show_uuid, show in directory_shows.items():
        assert show_uuid in catalog_shows, f"Show {show_uuid} in directory but not in catalog"
        catalog_show = catalog_shows[show_uuid]

        # Check that the show data is consistent
        assert show["title"] == catalog_show[
            "title"], f"Title mismatch for show {show_uuid}"
        assert show["url"] == catalog_show["url"], f"URL mismatch for show {show_uuid}"

        # Check that the episodes are consistent
        directory_episodes = {
            episode["uuid"]: episode for episode in show.get("episodes", [])}
        catalog_episodes = {episode_uuid: episode for episode_uuid, episode in catalog_data.get("episodes", {}).items()
                            if episode.get("show_uuid") == show_uuid}

        for episode_uuid, episode in directory_episodes.items():
            assert episode_uuid in catalog_episodes, f"Episode {episode_uuid} in directory but not in catalog"
            catalog_episode = catalog_episodes[episode_uuid]

            # Check that the episode data is consistent
            assert episode["title"] == catalog_episode[
                "title"], f"Title mismatch for episode {episode_uuid}"
            assert episode["url"] == catalog_episode[
                "url"], f"URL mismatch for episode {episode_uuid}"
