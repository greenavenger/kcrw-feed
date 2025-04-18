"""Module to handle state persistence"""

from datetime import datetime
from dataclasses import asdict
import json
import logging
import os
from typing import Any, Dict, Union, cast
import uuid

from atomicwrites import atomic_write

from kcrw_feed.persistence.base import BasePersister
from kcrw_feed.persistence.logger import TRACE_LEVEL_NUM
from kcrw_feed.models import Host, Show, Episode, Resource, ShowDirectory, Catalog
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

    def save(self, state: Union[ShowDirectory, Catalog], filename: str | None = None) -> None:
        """Save the given state object to a JSON file."""
        filename = filename or self.filename
        logger.info("Writing state file: %s", filename)

        # Convert to dictionary based on type. ShowDirectory is a list of shows,
        # and so can directly converted to a dict using asdict.
        if isinstance(state, ShowDirectory):
            data = asdict(state)
        else:  # Catalog is a dict of shows, episodes, hosts, and resources,
            # so we need to convert each to a dict by hand (taking care to
            # ensure that keys are str) and then add to the top-level dict
            # before calling asdict.
            data = {
                "type": "catalog",
                "shows": {str(k): asdict(v) for k, v in state.shows.items()},
                "episodes": {str(k): asdict(v) for k, v in state.episodes.items()},
                "hosts": {str(k): asdict(v) for k, v in state.hosts.items()},
                "resources": {k: asdict(v) for k, v in state.resources.items()}
            }

        with atomic_write(filename, mode="w", overwrite=True, encoding="utf-8") as f:
            json.dump(data, f, default=self.default_serializer, indent=2)

    # Deserialization helpers
    def _parse_datetime(self, date_str: str) -> datetime:
        """Assume ISO format dates."""
        return utils.parse_date(date_str)

    def _parse_uuid(self, uuid_str: str) -> uuid.UUID:
        """Assume valid UUID format."""
        return uuid.UUID(uuid_str)

    def episode_from_dict(self, data: Dict[Any, Any]) -> Episode:
        episode_uuid = self._parse_uuid(
            data.get("uuid")) if data.get("uuid") else None
        logger.debug("loading episode: %s [%s]", data.get("url"), episode_uuid)
        # TODO: Transition: uuid str -> uuid.UUID
        assert isinstance(
            episode_uuid, uuid.UUID) or isinstance(episode_uuid, str), "uuid is required for Episodes"
        resource = self.resource_from_dict(data.get("resource", {}))
        airdate = self._parse_datetime(
            data["airdate"]) if data.get("airdate") else None
        assert isinstance(
            airdate, datetime), "airdate is required for Episodes"
        show_uuid = self._parse_uuid(
            data.get("show_uuid")) if data.get("show_uuid") else None

        return Episode(
            title=data["title"],
            airdate=airdate,
            url=data["url"],
            media_url=data["media_url"],
            uuid=episode_uuid,
            show_uuid=show_uuid,
            # Hosts are stored by UUID in Episodes
            hosts=[self._parse_uuid(h) for h in data.get("hosts", []) if h],
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
        host_uuid = self._parse_uuid(
            data.get("uuid")) if data.get("uuid") else None
        logger.debug("loading host: %s [%s]", data.get("url"), host_uuid)
        # TODO: Transition: uuid str -> uuid.UUID
        assert isinstance(
            host_uuid, uuid.UUID) or isinstance(host_uuid, str), "uuid is required for Hosts"
        return Host(
            name=data["name"],
            uuid=host_uuid,
            title=data.get("title"),
            url=data.get("url"),
            image=data.get("image_url"),
            socials=data.get("socials", []),
            description=data.get("description"),
            type=data.get("type"),
            metadata=data.get("metadata", {})
        )

    def show_from_dict(self, data: Dict[Any, Any]) -> Show:
        show_uuid = self._parse_uuid(
            data.get("uuid")) if data.get("uuid") else None
        logger.debug("loading show: %s [%s]", data.get("url"), show_uuid)
        # TODO: Transition: uuid str -> uuid.UUID
        assert isinstance(
            show_uuid, uuid.UUID) or isinstance(show_uuid, str), "uuid is required for Shows"
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
            uuid=show_uuid,
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
            logger.debug("loading resource with url: %s", data.get("url"))
            last_updated = self._parse_datetime(data.get("last_updated"))
            lastmod = self._parse_datetime(
                data.get("metadata", {}).get("lastmod"))
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

    def catalog_from_dict(self, data: Dict[Any, Any]) -> Catalog:
        """Convert dictionary to Catalog object."""
        catalog = Catalog()

        # Process shows
        for show_id, show_data in data.get("shows", {}).items():
            show = self.show_from_dict(show_data)
            assert show.uuid is not None, "Failed to parse UUID for Show"
            catalog.shows[show.uuid] = show

            # Process episodes
            for episode in show.episodes:
                assert episode.uuid is not None, "Failed to parse UUID for Episode"
                catalog.episodes[episode.uuid] = episode

                # TODO: Should we store full Host entries?
                # Process hosts
                # for host in episode.hosts:
                #     if isinstance(host, uuid.UUID) and host not in catalog.hosts:
                #         # We need to find the host object
                #         for show_host in show.hosts:
                #             if show_host.uuid == host:
                #                 catalog.hosts[host] = show_host
                #                 break

                # Process resource
                if episode.resource:
                    catalog.resources[episode.resource.url] = episode.resource

            # Process show hosts
            for host in show.hosts:
                if host.uuid:
                    catalog.hosts[host.uuid] = host

            # Process show resource
            if show.resource:
                catalog.resources[show.resource.url] = show.resource

        return catalog

    def load(self, filename: str | None = None) -> Union[ShowDirectory, Catalog]:
        """Load the state from a JSON file and return a ShowDirectory or Catalog
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

        # Check if this is a Catalog or ShowDirectory
        if isinstance(data, dict) and "type" in data and data["type"] == "catalog":
            return self.catalog_from_dict(data)
        else:
            return self.directory_from_dict(data)
