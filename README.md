# KCRW Feed Generator

A CLI tool that scrapes KCRW.com music show data and generates RSS feeds for podcast players. It does not host audio files - only points to KCRW's servers.

## Installation

```bash
# Install dependencies
poetry install
```

## Quick Start

```bash
# List shows from local state
poetry run kcrw-feed list shows

# Show differences between local state and live site
poetry run kcrw-feed diff

# Update local state from kcrw.com
poetry run kcrw-feed update
```

## CLI Usage

```bash
poetry run kcrw-feed [options] <command> [args]
```

### Commands

| Command | Description |
| ------- | ----------- |
| `list [resources\|shows\|episodes\|hosts]` | List entities from local state (default: resources) |
| `diff [resources\|shows\|episodes\|hosts]` | Show differences between local state and kcrw.com |
| `update` | Update local state from kcrw.com and regenerate feeds |

### Global Options

| Option | Description |
| ------ | ----------- |
| `-v, --verbose` | Detailed output |
| `-n, --dry-run` | Preview changes without applying |
| `-m, --match REGEX` | Filter by URL pattern (e.g., `henry-rollins`, `dan-wilcox`) |
| `-s, --since DATE` | Filter by date (ISO 8601: `YYYY-MM-DDTHH:MM:SS`) |
| `-u, --until DATE` | Filter by date (ISO 8601: `YYYY-MM-DDTHH:MM:SS`) |
| `-o, --storage_root PATH` | Data directory for state/feeds |
| `-r, --source_root URL` | Source URL or local path |
| `-c, --config PATH` | Custom configuration file |
| `--loglevel LEVEL` | Log level: trace, debug, info, warning, error, critical |

### Examples

```bash
# List all shows
poetry run kcrw-feed list shows

# List episodes for a specific show
poetry run kcrw-feed -m "henry-rollins" list episodes

# Preview what would be updated (dry run)
poetry run kcrw-feed -n update

# Update episodes from the last week
poetry run kcrw-feed -s "2025-01-18" update

# Use verbose output
poetry run kcrw-feed -v list shows
```

## Architecture

### Data Flow

```
robots.txt → sitemaps → Resources → Shows/Episodes → JSON state → RSS feeds
```

1. **ResourceProcessor** - Parses `robots.txt` → sitemaps → extracts music show URLs as `Resource` objects
2. **StationProcessor** - Enriches Resources by fetching HTML/JSON, populating `Show` and `Episode` models
3. **StationCatalog** - Central repository holding all entities; `LocalStationCatalog` for persisted state, `LiveStationCatalog` for live kcrw.com data
4. **CatalogUpdater** - Compares local vs live catalogs, merges changes, triggers persistence
5. **Persisters** - Write state to JSON and generate RSS feeds

### Key Classes

- **Models** (`models.py`): `Resource`, `Show`, `Episode`, `Host`, `Catalog`, `FilterOptions`
- **Sources** (`source_manager.py`): `HttpsSource` (live HTTP with caching), `CacheSource` (local files)
- **Config** (`config.py`): YAML-based configuration with defaults in `kcrw_feed/data/default_config.yaml`

### State Management

- State persisted to JSON file (default: `kcrw_catalog.json`)
- HTTP responses cached via `requests_cache` (SQLite backend)
- Feeds written to `feeds/` directory

## Directory Structure

```
kcrw_feed/
├── main.py                # CLI entry point
├── models.py              # Show, Episode, Host, Resource, Catalog, etc.
├── config.py              # YAML-based configuration
├── source_manager.py      # HttpsSource, CacheSource
├── station_catalog.py     # LocalStationCatalog, LiveStationCatalog
├── updater.py             # CatalogUpdater
├── utils.py               # Utility functions
├── data/
│   └── default_config.yaml
├── persistence/
│   ├── feeds.py           # RSS feed generation
│   ├── state.py           # JSON state persistence
│   └── logger.py          # Custom JSON logging
└── processing/
    ├── resources.py       # ResourceProcessor (sitemap parsing)
    └── station.py         # StationProcessor (show/episode enrichment)
```

## Configuration

Default config at `kcrw_feed/data/default_config.yaml`. Override with `-c path/to/config.yaml`.

Key configuration options:
- `source_root` - KCRW website URL or local test data path
- `storage_root` - Directory for state files and feeds
- `state_file` - JSON state filename
- `feed_directory` - Directory for generated RSS feeds
- `http_cache` - Cache settings (directory, backend, expiration)
- `request_delay` - Throttling for live requests

## Testing

```bash
# Run all tests
poetry run pytest

# Run a specific test file
poetry run pytest tests/test_models.py

# Run a specific test
poetry run pytest tests/test_models.py::test_function_name -v

# Run tests with coverage
poetry run pytest --cov=kcrw_feed
```

### Integration Testing

Test data in `tests/data/` simulates KCRW site structure:

```bash
# Start local nginx to serve test data
cd tests/data && docker compose up -d

# Run against local test server
poetry run kcrw-feed --storage_root ./tests/data list
```

## Development

```bash
# Lint
poetry run pylint kcrw_feed
```

## License

This project is licensed under the GPL-3.0 License.

## Contact

If you have any questions or suggestions, please open an issue on the GitHub repository. You can also reach me by [email](mailto:cram%40greenavenger.com).
