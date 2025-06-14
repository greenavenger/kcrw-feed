"""Module to hold core dataclass objects"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Pattern
import uuid


@dataclass
class FilterOptions:
    """Options for filtering objects."""
    # e.g., a regex or substring to filter resource URLs
    match: Optional[str] = None
    compiled_match: Optional[Pattern] = None
    # TODO: do we need to filter on resource types?
    # e.g., ["resource", "show", "episode", "host"]
    # resource_types: Optional[List[str]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    dry_run: bool = False


@dataclass(order=True)
class Resource:
    """'metadata' is structured data extracted (and somewhat transformed)
    from xml data:

    metadata = {
      'changefreq': 'yearly',
      'image:image': {'image:loc': 'https://www.kcrw.com/music/shows/aaron-byrd/aaron-byrds-playlist-april-12-2021/@@images/image/page-header'},
      'lastmod': datetime.datetime(2021, 4, 13, 8, 12, 57, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=61200))),
      'loc': 'https://www.kcrw.com/music/shows/aaron-byrd/aaron-byrds-playlist-april-12-2021',
      'priority': '0.8'
    }
    """
    sort_index: str = field(init=False, repr=False)  # used for ordering
    url: str     # canonical location of resource on kcrw.com
    source: str  # source used: URL or path to local file
    last_updated: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Use the URL as the key for ordering.
        self.sort_index = self.url

    def __hash__(self):
        return hash(self.url)

    def __eq__(self, other: Resource):
        return self.url == other.url


@dataclass(order=True)
class Host:
    sort_index: str = field(init=False, repr=False)  # used for ordering
    name: str
    # TODO: Transition: uuid str -> uuid.UUID
    uuid: Optional[uuid.UUID | str] = None
    title: Optional[str] = None  # job title
    url: Optional[str] = None    # host page
    image: Optional[str] = None
    socials: List[Episode] = field(default_factory=list)
    description: Optional[str] = None
    type: Optional[str] = None
    # TODO: should we include the Show resource here? Note that both
    # a Show and an Episode have Host info (that could be conflicting
    # due to guest hosting).
    # host always comes with Show, and so does not have its own Resource
    # resource: Optional[Resource] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Use the URL as the key for ordering.
        self.sort_index = self.url

    def __hash__(self) -> int:
        if self.uuid is None:
            raise ValueError("Host must have a uuid to be hashable")
        return hash(self.uuid)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Host):
            return NotImplemented
        return self.uuid == other.uuid


@dataclass(order=True)
class Show:
    sort_index: str = field(init=False, repr=False)  # used for ordering
    title: str
    url: str
    image: str = "DEADBEEF"  # Optional[str] = None
    # TODO: Transition: uuid str -> uuid.UUID
    uuid: Optional[uuid.UUID | str] = None
    description: Optional[str] = None
    hosts: List[Host] = field(default_factory=list)
    episodes: List[Episode] = field(default_factory=list)
    type: Optional[str] = None
    last_updated: Optional[datetime] = None
    resource: Optional[Resource] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Use the URL as the key for ordering.
        self.sort_index = self.url

    def __hash__(self) -> int:
        if self.uuid is None:
            raise ValueError("Show must have a uuid to be hashable")
        return hash(self.uuid)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Show):
            return NotImplemented
        return self.uuid == other.uuid


@dataclass(order=True)
class Episode:
    sort_index: datetime = field(init=False, repr=False)  # used for ordering
    title: str
    airdate: datetime
    url: str
    media_url: str
    # TODO: Transition: uuid str -> uuid.UUID
    uuid: Optional[uuid.UUID | str] = None
    show_uuid: Optional[str] = None
    hosts: List[Host] = field(default_factory=list)
    description: Optional[str] = None
    songlist: Optional[str] = None
    image: Optional[str] = None
    type: Optional[str] = None
    duration: Optional[float] = None
    ending: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    resource: Optional[Resource] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Use the airdate as the sort index.
        self.sort_index = self.airdate

    def __hash__(self) -> int:
        if self.uuid is None:
            raise ValueError("Episode must have a uuid to be hashable")
        return hash(self.uuid)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Episode):
            return NotImplemented
        return self.uuid == other.uuid


@dataclass
class Catalog:
    """Catalog of shows, episodes, hosts, resources"""
    shows: Dict[uuid.UUID | str, Show] = field(default_factory=dict)
    episodes: Dict[uuid.UUID | str, Episode] = field(default_factory=dict)
    hosts: Dict[uuid.UUID | str, Host] = field(default_factory=dict)
    resources: Dict[str, Resource] = field(default_factory=dict)


@dataclass
class CatalogDiff:
    """Capture changes between two Catalogs"""
    added: List[Any] = field(default_factory=list)
    removed: List[Any] = field(default_factory=list)
    modified: List[ModifiedEntry] = field(default_factory=list)


@dataclass
class ModifiedEntry:
    """Capture the diff that we detected"""
    current: Any
    new: Any
    diff: Dict[str, Any]

    # Support asdict()
    def __post_init__(self):
        # If diff is a DeepDiff object, convert it to a dictionary
        if hasattr(self.diff, 'to_dict'):
            self.diff = self.diff.to_dict()


@dataclass
class ShowDirectory:
    # TODO: Add tests for this class
    shows: List[Show] = field(default_factory=list)
