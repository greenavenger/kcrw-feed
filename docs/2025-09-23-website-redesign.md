# KCRW.com Website Redesign (September 23, 2025)

On September 23, 2025, KCRW.com launched a major website redesign that changed the URL structure and data formats used throughout the site. This document summarizes the changes and how the feed scraper was updated to accommodate them.

## URL Structure Changes

### Show Pages

| Before | After |
|--------|-------|
| `/music/shows/{show-name}` | `/shows/{show-name}` |

Example:
- Old: `https://www.kcrw.com/music/shows/henry-rollins`
- New: `https://www.kcrw.com/shows/henry-rollins`

### Episode Pages

| Before | After |
|--------|-------|
| `/music/shows/{show}/{episode}` | `/shows/{show}/stories/{episode}` |

Example:
- Old: `https://www.kcrw.com/music/shows/henry-rollins/henry-rollins-kcrw-broadcast-877`
- New: `https://www.kcrw.com/shows/henry-rollins/stories/henry-rollins-kcrw-broadcast-877`

### Sitemaps

| Before | After |
|--------|-------|
| `/sitemap.xml.gz` (single compressed file) | `/sitemap-index.xml` (index pointing to multiple sitemaps) |
| Shows in `/sitemap-shows/music/sitemap.xml` | Shows in `/shows/sitemap.xml` |
| Episodes mixed with shows | Episodes in `/stories/sitemap/{0-22}.xml` |

## Data Format Changes

### Show Data

**Before:** Schema.org microdata embedded in HTML
```html
<body itemscope itemtype="http://schema.org/RadioSeries" itemid="uuid-here">
  <span itemprop="name">Show Title</span>
  <meta itemprop="description" content="..." />
</body>
```

**After:** Open Graph meta tags in `<head>`
```html
<head>
  <meta property="og:title" content="Show Title | KCRW" />
  <meta property="og:description" content="..." />
  <meta property="og:url" content="https://www.kcrw.com/shows/..." />
  <meta property="og:image" content="..." />
</head>
```

### Episode Data

**Before:** Dedicated JSON endpoint at `{episode-url}/player.json`
```json
{
  "title": "Episode Title",
  "airdate": "2025-01-23T20:00:00",
  "media": [{"url": "https://...mp3"}],
  "uuid": "...",
  "show_uuid": "..."
}
```

**After:** Data embedded in HTML page
- Title, description, URL: Open Graph meta tags
- Airdate: `<meta property="article:published_time">`
- Audio URL: Found as URL pattern in page content (e.g., `https://ondemand-media.kcrw.com/...mp3`)
- UUID: Not provided; generated deterministically from URL

## Technology Changes

The redesigned site uses:
- **Next.js** with React Server Components (RSC)
- **RSC payload** embedded in HTML as `self.__next_f.push([...])` scripts
- Standard SEO meta tags (Open Graph, Twitter Cards)

## Scraper Adaptations

### New PageDataParser Module

Created `kcrw_feed/processing/page_parser.py` to extract data from HTML meta tags:
- `get_og(property)` - Extract Open Graph meta content
- `get_title()` - Title from `og:title` or `<title>` tag
- `get_description()` - From `og:description`
- `get_published_time()` - From `article:published_time`
- `get_audio_url()` - Regex search for audio file URLs

### Updated URL Patterns

In `kcrw_feed/processing/resources.py`:
```python
# Sitemap filter: matches /shows/sitemap or /stories/sitemap/
SITEMAP_FILTER_RE = re.compile(r"(/shows/sitemap|/stories/sitemap/)")

# URL filter: matches /shows/{show}
SHOW_URL_RE = re.compile(r"/shows/[^/]+")
```

In `kcrw_feed/processing/station.py`:
```python
# Episode URLs have /stories/ segment
EPISODE_URL_REGEX = re.compile(r"/shows/[^/]+/stories/[^/]+")

# Extract show URL from episode URL
SHOW_FROM_EPISODE = re.compile(r'^(https?://[^/]+/shows/[^/]+)/stories/.*$')
```

### UUID Generation

Since the new site doesn't expose UUIDs in the HTML, we now generate deterministic UUIDs from URLs:
```python
uuid.uuid5(uuid.NAMESPACE_URL, resource.url)
```

This ensures the same URL always produces the same UUID, maintaining consistency across runs.

## Removed Code

The following are no longer used and were removed:
- `extruct` library for Schema.org microdata extraction
- `player.json` fetching and parsing
- `_parse_show_episodes()` method
- `_process_hosts()` method

## Testing

Test data was recaptured from the live site to reflect the new structure:
- `tests/data/shows/{show}/index.html` - Show pages
- `tests/data/shows/{show}/stories/{episode}/index.html` - Episode pages
- `tests/data/shows/sitemap.xml` - Shows sitemap
- `tests/data/stories/sitemap/0.xml` - Stories sitemap
