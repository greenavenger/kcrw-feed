"""Module to hold core dataclass objects"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class FilterOptions:
    # e.g., a regex or substring to filter resource URLs
    match: Optional[str] = None
    # e.g., ["resource", "show", "episode", "host"]
    resource_types: Optional[List[str]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    dry_run: bool = False


@dataclass
class Resource:
    url: str  # canonical location of resource on kcrw.com
    ref: str  # reference: URL or path to local file
    # metadata example:
    #   {'changefreq': 'yearly',
    #    'image:image': {'image:loc': 'https://www.kcrw.com/music/shows/aaron-byrd/aaron-byrds-playlist-april-12-2021/@@images/image/page-header'},
    #    'lastmod': datetime.datetime(2021, 4, 13, 8, 12, 57, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=61200))),
    #    'loc': 'https://www.kcrw.com/music/shows/aaron-byrd/aaron-byrds-playlist-april-12-2021',
    #    'priority': '0.8'}
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Host:
    name: str
    # Transition: uuid str -> uuid.UUID
    uuid: Optional[uuid.UUID | str] = None
    title: Optional[str] = None  # job title
    url: Optional[str] = None    # host page
    image_url: Optional[str] = None
    socials: List[Episode] = field(default_factory=list)
    description: Optional[str] = None
    type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(order=True)
class Show:
    sort_index: str = field(init=False, repr=False)  # used for ordering
    title: str
    url: str
    uuid: Optional[str] = None
    description: Optional[str] = None
    hosts: List[Host] = field(default_factory=list)
    episodes: List[Episode] = field(default_factory=list)
    type: Optional[str] = None
    last_updated: Optional[datetime] = None
    source_metadata: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Use the URL as the key for ordering.
        self.sort_index = self.url

    def update_info(self, new_data: Dict[str, Any]) -> None:
        """
        Update the show's information based on new data.
        Expected keys might include 'description', 'metadata', etc.
        """
        self.description = new_data.get("description", self.description)
        self.metadata.update(new_data.get("metadata", {}))
        self.last_updated = datetime.now()

    def add_episode(self, episode: Episode) -> None:
        """Append a new episode to the show's episode list."""
        if episode.uuid not in [e.uuid for e in self.episodes]:
            self.episodes.append(episode)

    def get_episodes(self) -> List[Episode]:
        return self.episodes

    def add_host(self, host: Host) -> None:
        """Append a new host to the show's host list."""
        self.hosts.append(host)

    def get_hosts(self) -> List[Host]:
        return self.hosts

    def needs_update(self) -> bool:
        """
        Determine whether the show needs updating.
        For example, if last_updated is None, or if a threshold has been exceeded.
        """
        return self.last_updated is None


@dataclass(order=True)
class Episode:
    sort_index: datetime = field(init=False, repr=False)  # used for ordering
    title: str
    airdate: datetime
    url: str
    media_url: str
    # Transition: uuid str -> uuid.UUID
    uuid: Optional[uuid.UUID | str | None] = None
    show_uuid: Optional[str] = None
    hosts: List[Host] = field(default_factory=list)
    description: Optional[str] = None
    songlist: Optional[str] = None
    image: Optional[str] = None
    type: Optional[str] = None
    duration: Optional[float] = None
    ending: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    source_metadata: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Use the airdate as the sort index.
        self.sort_index = self.airdate

    def get_hosts(self) -> List[Host] | None:
        if self.hosts:
            return self.hosts


@dataclass
class ShowDirectory:
    # TODO: Add tests for this class
    shows: List[Show] = field(default_factory=list)

    def add_show(self, show: Show) -> None:
        """Append a new show to the show directory."""
        self.shows.append(show)

    def get_show(self, uuid: str) -> Optional[Show]:
        """Return the show with the given UUID, if it exists."""
        for show in self.shows:
            if show.uuid == uuid:
                return show
        return None

    def get_shows(self, type: Optional[str] = None) -> List[Show]:
        """Return a list of shows with the given type."""
        if type:
            return [show for show in self.shows if show.type == type]
        return self.shows
