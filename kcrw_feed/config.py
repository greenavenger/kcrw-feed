"""Simple configuration reader"""

import yaml


def read_config(filename: str) -> dict[str, str]:
    """
    Reads a YAML configuration file and returns its contents as a dictionary.

    Parameters:
        filename (str): The path to the YAML configuration file.

    Returns:
        dict: The configuration data.
    """
    with open(filename, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config


CONFIG = read_config("config.yaml")
