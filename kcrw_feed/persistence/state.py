"""Module to handle state persistence"""

from datetime import datetime
from dataclasses import asdict
import json
import logging
import os
from typing import Any, Dict
import uuid

from kcrw_feed.persistence.base import BasePersister
from kcrw_feed.persistence.logger import TRACE_LEVEL_NUM
from kcrw_feed.models import Host, Show, Episode, Resource, ShowDirectory
from kcrw_feed import utils


logger = logging.getLogger("kcrw_feed")


class StatePersister(BasePersister):
    """Concrete implementation for storing and retrieving state."""

    def __init__(self, storage_root: str, state_file: str) -> None:
        self.filename = os.path.abspath(os.path.join(storage_root, state_file))
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
        logger.info("Writing state file: %s", filename)
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
            image=data.get("image_url"),
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
        assert data["image"] != "DEADBEEF"
        return Show(
            title=data["title"],
            url=data["url"],
            image=data["image"],
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
        assert filename.endswith(
            ".json"), "State file must be JSON: {filename}"
        logger.info("Reading state file: %s", filename)
        if not os.path.exists(filename):
            logger.info(
                "State file does not exist. Returning empty ShowDirectory.")
            return ShowDirectory(shows=[])
        with open(filename, "rb") as f:
            raw = f.read()
            logger.debug("Read %d bytes from %s", len(raw), filename)
            data = json.loads(raw.decode("utf-8"))
        return self.directory_from_dict(data)
