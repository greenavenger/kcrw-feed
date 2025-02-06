"""Module to hold core dataclass objects"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class Host:
    name: str
    uuid: Optional[str] = None
    title: Optional[str] = None  # job title
    url: Optional[str] = None  # host page
    image_url: Optional[str] = None
    twitter: Optional[str] = None
    description: Optional[str] = None
    shows: List[Show] = field(default_factory=list)

    def add_show(self, show: Show) -> None:
        """Add a show to this host's list of shows."""
        self.shows.append(show)

    def get_active_shows(self) -> List[Show]:
        """Return a list of shows that need updating.

        Currently, this returns all shows.
        """
        return self.shows


@dataclass
class Show:
    title: str
    url: str
    uuid: Optional[str] = None
    description: Optional[str] = None
    episodes: List[Episode] = field(default_factory=list)
    last_updated: Optional[datetime] = None
    metadata: Dict = field(default_factory=dict)

    def update_info(self, new_data: dict) -> None:
        """
        Update the show's information based on new data.
        Expected keys might include 'description', 'metadata', etc.
        """
        self.description = new_data.get("description", self.description)
        self.metadata.update(new_data.get("metadata", {}))
        self.last_updated = datetime.now()

    def add_episode(self, episode: Episode) -> None:
        """Append a new episode to the show's episode list."""
        self.episodes.append(episode)

    def needs_update(self) -> bool:
        """
        Determine whether the show needs updating.
        For example, if last_updated is None, or if a threshold has been exceeded.
        """
        return self.last_updated is None


@dataclass
class Episode:
    title: str
    pub_date: datetime
    audio_url: str
    uuid: Optional[str] = None
    description: Optional[str] = None
