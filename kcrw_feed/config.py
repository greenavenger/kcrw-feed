"""Simple configuration reader"""

from typing import Any, Dict
import sys
import yaml

CONFIG_FILE = "config.yaml"


def read_config(filename: str) -> Dict[str, Any]:
    """
    Reads a YAML configuration file and returns its contents as a dictionary.

    Parameters:
        filename (str): The path to the YAML configuration file.

    Returns:
        dict: The configuration data.
    """
    with open(filename, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    validate_config(config)
    return config


def validate_config(config: Dict[str, Any]) -> None:
    if not config.get("source_root"):
        print(
            f"Config file {CONFIG_FILE} missing required entry: 'source_root'")
        sys.exit(1)


CONFIG = read_config(CONFIG_FILE)
