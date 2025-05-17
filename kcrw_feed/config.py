"""Simple configuration reader and filter option parser"""

import argparse
from datetime import datetime, timezone, timedelta
import re
import sys
import time
from typing import Any, Dict, Optional, Pattern
import yaml
from importlib import resources

from kcrw_feed.models import FilterOptions


class Config:
    """Manages configuration for the KCRW Feed Generator."""

    def __init__(self, custom_config_path: Optional[str] = None):
        """
        Initialize configuration from default and optional custom config.

        Args:
            custom_config_path: Optional path to a custom YAML config file.
        """
        self._config = self._load_config(custom_config_path)
        self._validate_config()

    @staticmethod
    def _get_default_config_path() -> str:
        """Get the path to the default config file in the package."""
        with resources.files('kcrw_feed').joinpath('data/default_config.yaml').open('r') as f:
            return f.name

    def _load_config(self, custom_config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load configuration from default and optional custom config file.

        Args:
            custom_config_path: Optional path to a custom YAML config file.

        Returns:
            Dict containing merged configuration.
        """
        # Always load the default config first
        default_path = self._get_default_config_path()
        with open(default_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # If a custom config is specified, override top-level values
        if custom_config_path:
            with open(custom_config_path, 'r', encoding='utf-8') as f:
                custom_config = yaml.safe_load(f)
                # Simple top-level override
                config.update(custom_config)

        return config

    def _validate_config(self) -> None:
        """Validate the configuration dictionary."""
        if not self._config.get("source_root"):
            print(f"Config file missing required entry: 'source_root'",
                  file=sys.stderr)
            sys.exit(1)

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-like access to config values."""
        return self._config[key]

    def __contains__(self, key: str) -> bool:
        """Support 'in' operator for checking key existence."""
        return key in self._config

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value with optional default."""
        return self._config.get(key, default)


def get_local_timezone() -> timezone:
    """Use local timezone for command line arguments."""
    if time.daylight and time.localtime().tm_isdst:
        offset = -time.altzone
    else:
        offset = -time.timezone
    return timezone(timedelta(seconds=offset))


def parse_datetime(dt_str: str) -> datetime:
    """Append timezone info."""
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=get_local_timezone())
    return dt


def get_filter_options(args: argparse.Namespace) -> FilterOptions:
    """
    Populate a FilterOptions instance based on parsed command-line arguments.

    Expects:
      args.match: Optional[str] - a regex or substring to filter resource URLs.
      args.since: Optional[str] - an ISO 8601 timestamp (e.g. "YYYY-MM-DDTHH:MM:SS")
      args.until: Optional[str] - an ISO 8601 timestamp.
      args.dry_run: bool - indicates whether to perform a dry run.

    Returns:
      FilterOptions: populated instance.
    """
    # Validate and compile the match pattern if provided.
    compiled_match: Optional[Pattern[str]] = None
    if getattr(args, "match", None):
        pattern_str = args.match
        if not any(ch in pattern_str for ch in "[]()?*+|^$\\"):
            pattern_str = f".*{pattern_str}.*"
        try:
            # Make matches case insensitive for simplicity
            compiled_match = re.compile(pattern_str, re.IGNORECASE)
        except re.error as e:
            raise ValueError(
                f"Invalid regex provided for --match: {args.match}. Error: {e}") from None

    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    if getattr(args, "since", None):
        try:
            start_date = parse_datetime(args.since)
        except ValueError:
            raise ValueError(f"Invalid 'since' timestamp: {args.since}")

    if getattr(args, "until", None):
        try:
            end_date = parse_datetime(args.until)
        except ValueError:
            raise ValueError(f"Invalid 'until' timestamp: {args.until}")

    # TODO: do we need to filer on resource types
    # If you later want to support resource types via a flag (e.g. --resource_types)
    # resource_types: Optional[List[str]] = None
    # if hasattr(args, "resource_types") and args.resource_types:
    #     # Expect comma-separated list
    #     resource_types = [x.strip() for x in args.resource_types.split(",")]

    return FilterOptions(
        match=args.match,
        compiled_match=compiled_match,
        # resource_types=resource_types,
        start_date=start_date,
        end_date=end_date,
        dry_run=args.dry_run,
    )
