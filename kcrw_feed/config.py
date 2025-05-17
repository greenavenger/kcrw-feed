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


def get_default_config_path() -> str:
    """Get the path to the default config file in the package."""
    # For Python 3.9+, we can use files() which returns a Traversable
    with resources.files('kcrw_feed').joinpath('data/default_config.yaml').open('r') as f:
        return f.name


def read_config(filename: Optional[str] = None) -> Dict[str, Any]:
    """
    Reads configuration files and returns their contents as a dictionary.
    If a custom config file is specified, its top-level values override the defaults.
    Note: For nested structures like logging, the entire structure must be provided
    in the custom config to override the default.

    Parameters:
        filename (str): The path to a custom YAML configuration file. If None, uses only package default.

    Returns:
        dict: The configuration data with custom overrides.
    """
    # Always load the default config first
    default_path = get_default_config_path()
    with open(default_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # If a custom config is specified, override top-level values
    if filename:
        with open(filename, 'r', encoding='utf-8') as f:
            custom_config = yaml.safe_load(f)
            # Simple top-level override
            config.update(custom_config)

    validate_config(config)
    return config


def validate_config(config: Dict[str, Any]) -> None:
    """Validate the configuration dictionary."""
    if not config.get("source_root"):
        print(f"Config file missing required entry: 'source_root'")
        sys.exit(1)


# Initialize configuration with package defaults
# CONFIG = read_config()


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
