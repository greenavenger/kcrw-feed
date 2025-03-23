"""Module to handle state persistence"""

from abc import ABC, abstractmethod
from datetime import datetime
from dataclasses import asdict
import json
import logging
import os
from typing import Any, Dict
import uuid

from django.utils.feedgenerator import Rss201rev2Feed

from kcrw_feed.persistence.logger import TRACE_LEVEL_NUM
from kcrw_feed.models import Host, Show, Episode, Resource, ShowDirectory
from kcrw_feed import utils


FILENAME_JSON: str = "kcrw_feed.json"
FEED_DIRECTORY: str = "feeds/"

logger = logging.getLogger("kcrw_feed")


class BasePersister(ABC):
    @abstractmethod
    def save(self, state: ShowDirectory, filename: str) -> None:
        pass

    @abstractmethod
    def load(self, filename: str) -> ShowDirectory:
        pass


class JsonPersister(BasePersister):
    def __init__(self, storage_root: str, filename: str = FILENAME_JSON) -> None:
        self.filename = os.path.join(storage_root, filename)
        logger.debug("JSON file: %s", self.filename)

    # Serialization
    def default_serializer(self, obj: Any) -> Any:
        """Helper to convert non-serializable objects like datetime."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        raise TypeError(f"Type {type(obj)} not serializable")

    def save(self, directory: ShowDirectory, filename: str | None = None) -> None:
        """Save the given ShowDirectory object's state to a JSON file."""
        filename = filename or self.filename
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(asdict(directory), f,
                      default=self.default_serializer, indent=2)

    # Deserialization helpers
    def _parse_datetime(self, date_str: str) -> datetime:
        """Assume ISO format dates."""
        return utils.parse_date(date_str)

    def _parse_uuid(self, uuid_str: str) -> uuid.UUID:
        """Assume valid UUID format."""
        return uuid.UUID(uuid_str)

    def episode_from_dict(self, data: Dict[Any, Any]) -> Episode:
        resource = self.resource_from_dict(data.get("resource", {}))
        return Episode(
            title=data["title"],
            airdate=self._parse_datetime(
                data["airdate"]) if data.get("airdate") else None,
            url=data["url"],
            media_url=data["media_url"],
            uuid=self._parse_uuid(data.get("uuid")),
            show_uuid=self._parse_uuid(data.get("show_uuid")),
            # Hosts are stored by UUID in Episodes
            # hosts=[self.host_from_dict(h) for h in data.get("hosts", [])],
            hosts=[self._parse_uuid(h) for h in data.get("hosts", [])],
            description=data.get("description"),
            songlist=data.get("songlist"),
            image=data.get("image"),
            type=data.get("type"),
            duration=data.get("duration"),
            ending=self._parse_datetime(
                data["ending"]) if data.get("ending") else None,
            last_updated=self._parse_datetime(
                data["last_updated"]) if data.get("last_updated") else None,
            resource=resource,
            metadata=data.get("metadata", {})
        )

    def host_from_dict(self, data: Dict[Any, Any]) -> Host:
        return Host(
            name=data["name"],
            uuid=self._parse_uuid(data.get("uuid")),
            title=data.get("title"),
            url=data.get("url"),
            image_url=data.get("image_url"),
            socials=data.get("socials", []),
            description=data.get("description"),
            type=data.get("type"),
            metadata=data.get("metadata", {})
        )

    def show_from_dict(self, data: Dict[Any, Any]) -> Show:
        episodes = [self.episode_from_dict(ep)
                    for ep in data.get("episodes", [])]
        hosts = [self.host_from_dict(h) for h in data.get("hosts", [])]
        resource = self.resource_from_dict(data.get("resource", {}))
        last_updated = self._parse_datetime(
            data["last_updated"]) if data.get("last_updated") else None
        return Show(
            title=data["title"],
            url=data["url"],
            uuid=self._parse_uuid(data.get("uuid")),
            description=data.get("description"),
            hosts=hosts,
            episodes=episodes,
            type=data.get("type"),
            last_updated=last_updated,
            resource=resource,
            metadata=data.get("metadata", {})
        )

    def resource_from_dict(self, data: Dict[str, Any]) -> Resource:
        if data:
            last_updated = self._parse_datetime(data.get("last_updated"))
            lastmod = self._parse_datetime(data.get("metadata")["lastmod"])
            resource = Resource(
                url=data["url"],
                source=data.get("source", ""),
                last_updated=last_updated,
                metadata=data.get("metadata", {})
            )
            resource.metadata["lastmod"] = lastmod
            return resource
        return Resource(url="", source="", metadata={})

    def directory_from_dict(self, data: Dict[Any, Any]) -> ShowDirectory:
        shows = [self.show_from_dict(show_data)
                 for show_data in data.get("shows", [])]
        return ShowDirectory(shows=shows)

    def load(self, filename: str | None = None) -> ShowDirectory:
        """Load the state from a JSON file and return a ShowDirectory
        instance."""
        filename = filename or self.filename
        if not os.path.exists(filename):
            logger.debug(
                "File %s does not exist. Returning empty ShowDirectory.", filename)
            return ShowDirectory(shows=[])
        with open(filename, "rb") as f:
            raw = f.read()
            logger.debug("Read %d bytes from %s", len(raw), filename)
            data = json.loads(raw.decode("utf-8"))
        return self.directory_from_dict(data)


class RssPersister(BasePersister):
    def __init__(self, storage_root: str, feed_dir: str = FEED_DIRECTORY) -> None:
        self.feed_dir = os.path.join(storage_root, feed_dir)
        logger.debug("RSS output directory: %s", self.feed_dir)

    def save(self, show_directory: ShowDirectory, feed_dir: str | None = None) -> None:
        """Generate an individual RSS feed XML file for each show in the state.
        Episodes are sorted in reverse chronological order (most recent first).

        Parameters:
          state: A ShowDirectory instance containing a list of shows.
          output_dir: The output directory where feed files will be written."""
        feed_dir = feed_dir or self.feed_dir
        os.makedirs(feed_dir, exist_ok=True)
        for show in show_directory.shows:
            # Create an RSS feed using Django's feed generator.
            feed = Rss201rev2Feed(
                title=show.title,
                link=show.url,
                description=show.description or "",
                language="en"
            )
            # Sort episodes: most recent first.
            episodes = sorted(
                [ep for ep in show.episodes if ep.airdate is not None], reverse=True)
            for ep in episodes:
                feed.add_item(
                    title=ep.title,
                    link=ep.media_url,
                    description=ep.description or "",
                    pubdate=ep.airdate
                )
            # Generate the XML as a string.
            feed_xml = feed.writeString("utf-8")
            # Use the show's UUID as the filename (or fallback to title).
            file_name = f"{show.title}.xml" if show.title else f"{show.uuid}.xml"
            output_path = os.path.join(feed_dir, file_name)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(feed_xml)

    def load(self, filename: str) -> ShowDirectory:
        raise NotImplementedError("RSS load not implemented")
