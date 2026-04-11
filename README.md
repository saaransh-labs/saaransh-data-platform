# Saaransh Data Platform

A data platform for collecting and normalizing equity market data from the [National Stock Exchange of India (NSE)](https://www.nseindia.com). Currently supports scraping Nifty 500 constituent metadata with async HTTP, rate limiting, cookie management, and retry logic.

## Features

- Async concurrent fetching via `aiohttp` with a configurable concurrency limit
- Rate limiter enforcing a minimum interval between consecutive requests
- Automatic cookie bootstrapping — visits the NSE homepage to acquire session cookies before API calls
- 403 recovery — refreshes cookies on a block, with a lock to prevent stampedes
- Exponential back-off with jitter on retries
- Per-stage HTTP timeouts (`connect`, `sock_read`, `total`)
- Raw responses persisted as individual JSON files
- Normalized output saved as a monthly JSON snapshot

## Project Structure

```
saaransh-data-platform/
├── config/
│   └── data_sources.yaml       # NSE API endpoints and config
├── data/                       # Output data (gitignored)
│   ├── raw/metadata/           # Per-symbol raw JSON responses
│   └── parsed/                 # Normalized monthly snapshots
├── docs/
│   └── adr/                    # Architecture Decision Records
├── experiments/                # Jupyter notebooks
├── src/
│   ├── common/
│   │   ├── path.py             # Project-root-relative path constants
│   │   └── utils.py            # YAML loader and shared helpers
│   └── data_source/
│       └── nse/
│           ├── models.py       # Company dataclass
│           ├── normalizer.py   # Raw JSON → Company normalizer
│           └── scraper.py      # Async NSE scraper
└── pyproject.toml
```

## Requirements

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) for dependency and environment management

## Setup

```bash
# Clone the repo
git clone <repo-url>
cd saaransh-data-platform

# Install dependencies
uv sync

# (Optional) Install notebook output stripping — required if you work with Jupyter notebooks
uv add --dev nbstripout
nbstripout install
```

> See [ADR 001](docs/adr/001-notebook-output-stripping.md) for why `nbstripout` is used as a git filter rather than a pre-commit hook.

## Usage

### Fetch all 500 Nifty 500 constituents

```bash
uv run src/data_source/nse/scraper.py
```

### Fetch a limited number of symbols (useful for testing)

```bash
uv run src/data_source/nse/scraper.py --limit 10
```

### Write raw JSON to a custom directory

```bash
uv run src/data_source/nse/scraper.py --output-dir /tmp/nse-data
```

After a successful run, two outputs are produced:

| Output | Location | Description |
|---|---|---|
| Raw responses | `data/raw/metadata/<SYMBOL>.json` | Full NSE API response per symbol |
| Normalized snapshot | `data/parsed/companies_YYYY_MM.json` | Structured company records for the current month |

## Configuration

All API endpoints are defined in `config/data_sources.yaml`:

```yaml
data_sources:
  nse:
    url: "https://www.nseindia.com"
    nifty500:
      url: "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    market_data:
      url: "https://www.nseindia.com/api/quote-equity?symbol={symbol}"
      reference: "https://www.nseindia.com/get-quotes/equity?symbol={symbol}"
```

Scraping parameters (concurrency, retries, rate limit interval) are defined as module-level constants at the top of `src/data_source/nse/scraper.py`.

## Architecture Decisions

| ADR | Title |
|---|---|
| [001](docs/adr/001-notebook-output-stripping.md) | Notebook output stripping with nbstripout |
| [002](docs/adr/002-NSE-scaper-improvement.md) | NSE scraper concurrency and reliability improvements |

## Roadmap

- [ ] Structured logging
- [ ] REST API layer
- [ ] Monitoring and alerting
- [ ] Standardized error codes
- [ ] Job persistence and resumability
- [ ] Data versioning
- [ ] Storage backends: S3 and MinIO
