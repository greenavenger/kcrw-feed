"""Tests for configuration management and filter option parser"""

import argparse
import os
import re
import tempfile
import yaml
import pytest
from datetime import datetime
from typing import Dict, Any

from kcrw_feed.config import Config, read_config, get_filter_options, get_local_timezone
from kcrw_feed.models import FilterOptions

# --- Tests for Config class and read_config ---


def test_config_valid(tmp_path: os.PathLike) -> None:
    """
    Create a temporary YAML config file with a valid 'source_root'
    and verify that Config loads it correctly.
    """
    config_data: Dict[str, Any] = {
        "source_root": "https://www.example.com/",
        "storage_root": ".",
        "state_file": "catalog/state.xml",
        "feed_directory": "catalog/feeds"
    }
    config_file = os.path.join(tmp_path, "test_config.yaml")
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f)

    config = Config(config_file)
    assert config["source_root"] == "https://www.example.com/"
    assert config["storage_root"] == "."
    assert config["state_file"] == "catalog/state.xml"
    assert config["feed_directory"] == "catalog/feeds"


def test_config_override_defaults(tmp_path: os.PathLike) -> None:
    """
    Create a YAML config file that overrides some default values and verify
    that Config merges them correctly.
    """
    config_data: Dict[str, Any] = {
        "source_root": "https://custom.example.com/",
        "http_timeout": 30,
        "request_delay": {
            "mean": 10.0,
            "stddev": 3.0
        }
    }
    config_file = os.path.join(tmp_path, "test_config.yaml")
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f)

    config = Config(config_file)
    # Verify overridden values
    assert config["source_root"] == "https://custom.example.com/"
    assert config["http_timeout"] == 30
    assert config["request_delay"]["mean"] == 10.0
    assert config["request_delay"]["stddev"] == 3.0
    # Verify default values are still present
    assert "storage_root" in config
    assert "state_file" in config
    assert "feed_directory" in config
    assert "request_headers" in config


def test_config_get_with_default() -> None:
    """Test Config.get() method with default value."""
    config = Config()
    assert config.get("nonexistent_key", "default") == "default"
    # Should return actual value
    assert config.get("source_root", "default") != "default"


def test_read_config_legacy(tmp_path: os.PathLike) -> None:
    """
    Test the legacy read_config function for backward compatibility.
    """
    config_data: Dict[str, Any] = {
        "source_root": "https://www.example.com/",
        "storage_root": "."
    }
    config_file = os.path.join(tmp_path, "test_config.yaml")
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f)

    result = read_config(config_file)
    assert isinstance(result, dict)
    assert result["source_root"] == "https://www.example.com/"
    assert result["storage_root"] == "."

# --- Tests for get_filter_options ---


def test_get_filter_options_valid_substring() -> None:
    """
    Test get_filter_options when --match is provided as a substring.
    It should compile the regex as ".*<substring>.*" if no regex metacharacters are found.
    """
    args = argparse.Namespace(
        match="test",
        since="2025-01-01T00:00:00",
        until="2025-01-02T00:00:00",
        dry_run=True
    )
    filter_opts: FilterOptions = get_filter_options(args)
    # The original match string remains stored.
    assert filter_opts.match == "test"
    # A compiled regex should be present. Since "test" has no special characters,
    # it gets wrapped to ".*test.*"
    assert filter_opts.compiled_match is not None
    assert filter_opts.compiled_match.pattern == ".*test.*"
    # Use the local timezone for expected datetimes.
    local_tz = get_local_timezone()
    expected_start = datetime.fromisoformat(
        "2025-01-01T00:00:00").replace(tzinfo=local_tz)
    expected_end = datetime.fromisoformat(
        "2025-01-02T00:00:00").replace(tzinfo=local_tz)
    assert filter_opts.start_date == expected_start
    assert filter_opts.end_date == expected_end
    assert filter_opts.dry_run is True


def test_get_filter_options_valid_regex() -> None:
    """
    Test get_filter_options when --match is provided as a valid regex containing
    special characters. In that case, the pattern should not be wrapped.
    """
    regex_input = r"^show\d+$"
    args = argparse.Namespace(
        match=regex_input,
        since=None,
        until=None,
        dry_run=False
    )
    filter_opts: FilterOptions = get_filter_options(args)
    assert filter_opts.match == regex_input
    assert filter_opts.compiled_match is not None
    assert filter_opts.compiled_match.pattern == regex_input


def test_get_filter_options_invalid_regex() -> None:
    """
    Test that get_filter_options raises a ValueError if --match is an invalid regex.
    """
    args = argparse.Namespace(
        match="roll**ins",  # Invalid regex: multiple repeat error.
        since=None,
        until=None,
        dry_run=False
    )
    with pytest.raises(ValueError) as exc_info:
        get_filter_options(args)
    assert "Invalid regex provided for --match" in str(exc_info.value)


def test_get_filter_options_invalid_since() -> None:
    """
    Test that get_filter_options raises a ValueError if --since is not a valid ISO timestamp.
    """
    args = argparse.Namespace(
        match=None,
        since="invalid-date",
        until=None,
        dry_run=False
    )
    with pytest.raises(ValueError) as exc_info:
        get_filter_options(args)
    assert "Invalid 'since' timestamp" in str(exc_info.value)


def test_get_filter_options_invalid_until() -> None:
    """
    Test that get_filter_options raises a ValueError if --until is not a valid ISO timestamp.
    """
    args = argparse.Namespace(
        match=None,
        since=None,
        until="2025-13-01T00:00:00",  # invalid month
        dry_run=False
    )
    with pytest.raises(ValueError) as exc_info:
        get_filter_options(args)
    assert "Invalid 'until' timestamp" in str(exc_info.value)
