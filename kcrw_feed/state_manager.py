"""Module to handle state persistence"""

import json
from datetime import datetime
from dataclasses import asdict
from typing import Any, Dict
import uuid

from kcrw_feed.models import Host, Show, Episode
from kcrw_feed import utils


class Json:
    def __init__(self, filename: str = "kcrw_feed.json") -> None:
        self.filename = filename

    # Serialization
    def default_serializer(self, obj: Any) -> Any:
        """Helper to convert non-serializable objects like datetime."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    def save_state(self, show: Show, filename: str | None = None) -> None:
        """
        Save the given Show object's state to a JSON file.
        """
        filename = filename or self.filename
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(asdict(show), f,
                      default=self.default_serializer, indent=2)

    # Deserialization helpers
    def _parse_datetime(self, date_str: str) -> datetime:
        """Assume ISO format dates."""
        return utils.parse_date(date_str)

    def _parse_uuid(self, uuid_str: str) -> uuid.UUID:
        """Assume valid UUID format."""
        return uuid.UUID(uuid_str)

    def episode_from_dict(self, data: Dict[Any, Any]) -> Episode:
        return Episode(
            title=data["title"],
            airdate=self._parse_datetime(
                data["airdate"]) if data.get("airdate") else None,
            url=data["url"],
            media_url=data["media_url"],
            uuid=data.get("uuid"),
            show_uuid=data.get("show_uuid"),
            hosts=[self.host_from_dict(h) for h in data.get("hosts", [])],
            description=data.get("description"),
            songlist=data.get("songlist"),
            image=data.get("image"),
            type=data.get("type"),
            duration=data.get("duration"),
            ending=self._parse_datetime(
                data["ending"]) if data.get("ending") else None,
            last_updated=self._parse_datetime(
                data["last_updated"]) if data.get("last_updated") else None,
            metadata=data.get("metadata", {})
        )

    def host_from_dict(self, data: Dict[Any, Any]) -> Host:
        return Host(
            name=data["name"],
            uuid=data.get("uuid"),
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
        last_updated = self._parse_datetime(
            data["last_updated"]) if data.get("last_updated") else None
        return Show(
            title=data["title"],
            url=data["url"],
            uuid=data.get("uuid"),
            description=data.get("description"),
            hosts=hosts,
            episodes=episodes,
            type=data.get("type"),
            last_updated=last_updated,
            metadata=data.get("metadata", {})
        )

    def load_state(self, filename: str | None = None) -> Show:
        """
        Load the Show object's state from a JSON file and return a Show instance.
        """
        filename = filename or self.filename
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self.show_from_dict(data)
