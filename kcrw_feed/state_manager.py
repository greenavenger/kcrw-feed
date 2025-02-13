"""Module to handle state persistence"""

import json
from datetime import datetime
from dataclasses import asdict

from kcrw_feed.models import Host, Show, Episode


class Json:
    def __init__(self, filename: str = "kcrw_feed.json") -> None:
        self.filename = filename

    # Serialization
    def default_serializer(self, obj):
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
    def _parse_datetime(self, dt_str: str) -> datetime:
        """Assume ISO format dates."""
        return datetime.fromisoformat(dt_str)

    def episode_from_dict(self, data: dict) -> Episode:
        return Episode(
            title=data["title"],
            airdate=self._parse_datetime(
                data["pub_date"]) if data.get("pub_date") else None,
            audio_url=data["audio_url"],
            uuid=data.get("uuid"),
            description=data.get("description")
        )

    def host_from_dict(self, data: dict) -> Host:
        return Host(
            name=data["name"],
            uuid=data.get("uuid"),
            title=data.get("title"),
            url=data.get("url"),
            image_url=data.get("image_url"),
            twitter=data.get("twitter"),
            description=data.get("description")
        )

    def show_from_dict(self, data: dict) -> Show:
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
