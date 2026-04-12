"""
nse_scraper.py

Asynchronous scraper for fetching equity market data from the NSE India API.

Fetches quote data for a list of stock symbols concurrently, with built-in
rate limiting, cookie management, and exponential-backoff retry logic.
Results are persisted as individual JSON files in a configurable output directory.
"""

import json
import random
import asyncio
import aiohttp
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# NSE API endpoints
# ---------------------------------------------------------------------------
NSE_BASE_URL = "https://www.nseindia.com"
MARKET_DATA_URL = "https://www.nseindia.com/api/quote-equity?symbol="
REFERER_URL = "https://www.nseindia.com/get-quotes/equity?symbol="

# Base HTTP headers shared across all requests.
# NSE requires a browser-like User-Agent and a symbol-specific Referer to
# serve API responses; without them requests are typically rejected with 403.
BASE_HEADER = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

# ---------------------------------------------------------------------------
# Tunable scraping parameters
# ---------------------------------------------------------------------------
MAX_RETRIES = 3          # Maximum number of fetch attempts per symbol
MAX_CONCURRENT = 3       # Maximum number of in-flight requests at any time
BASE_DELAY_MIN = 1       # Minimum base delay (seconds) used for jitter calculations
BASE_DELAY_MAX = 4       # Maximum base delay (seconds) used for jitter calculations
RATE_LIMIT_INTERVAL = 1.0  # Minimum interval (seconds) between consecutive requests
OUTPUT_DIR = Path("experiments/exp_001_nifty_500_metadata/data")  # Default directory for persisted JSON files


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def get_headers(symbol: str) -> dict[str, str]:
    """
    Build request headers for a specific stock symbol.

    Merges the shared base headers with a symbol-specific ``Referer`` value,
    which is required by the NSE API to validate the request origin.

    Args:
        symbol: The NSE stock symbol (e.g. ``"RELIANCE"``).

    Returns:
        A dictionary of HTTP headers ready to be passed to an aiohttp request.
    """
    return {
        **BASE_HEADER,
        "Referer": f"{REFERER_URL}{symbol}",
    }


def save_to_file(symbol: str, data: dict, output_dir: Path) -> None:
    """
    Persist the fetched market data for a symbol to a JSON file.

    The file is named ``<symbol>.json`` and written inside *output_dir*.

    Args:
        symbol: The NSE stock symbol used as the filename stem.
        data: The parsed JSON response body to persist.
        output_dir: Directory in which the file will be written.
    """
    output_file = output_dir / f"{symbol}.json"
    with open(output_file, "w") as f:
        f.write(json.dumps(data, indent=4))


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

class ResultManager:
    """
    Tracks fetch outcomes and persists successful results to disk.

    Maintains running counts across four categories — *total*, *success*,
    *failed* (``None`` result after all retries), and *empty* (API returned
    an empty payload) — and writes successful responses as JSON files.
    """

    def __init__(self, output_dir: Path) -> None:
        """
        Args:
            output_dir: Directory where successful results will be saved.
                        Created automatically if it does not exist.
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "empty": 0,
        }

    def update(self, symbol: str, result: Optional[dict]) -> None:
        """
        Record the outcome for a single symbol fetch attempt.

        Increments the appropriate counter and, on success, writes the
        result to disk via :func:`save_to_file`.

        Args:
            symbol: The stock symbol that was fetched.
            result: The parsed API response, an empty dict on empty payload,
                    or ``None`` if all retry attempts failed.
        """
        self.stats["total"] += 1

        if result is None:
            # All retry attempts were exhausted without a valid response.
            self.stats["failed"] += 1
        elif not result:
            # Request succeeded but the API returned an empty body.
            self.stats["empty"] += 1
        else:
            self.stats["success"] += 1
            save_to_file(symbol, result, self.output_dir)

    def report(self) -> None:
        """Print a one-line summary of fetch statistics to stdout."""
        print(
            f"Total: {self.stats['total']}, "
            f"Success: {self.stats['success']}, "
            f"Failed: {self.stats['failed']}, "
            f"Empty: {self.stats['empty']}"
        )


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    Async token-bucket style rate limiter that enforces a minimum interval
    between consecutive acquisitions.

    A single asyncio ``Lock`` serialises callers so that at most one request
    is released every *min_interval* seconds, even under heavy concurrency.
    """

    def __init__(self, min_interval: float) -> None:
        """
        Args:
            min_interval: Minimum number of seconds that must elapse between
                          successive calls to :meth:`acquire`.
        """
        self.min_interval = min_interval
        self._lock = asyncio.Lock()
        self._last_call: float = 0.0

    async def acquire(self) -> None:
        """
        Wait until the rate-limit window has elapsed, then record the current
        time as the most recent call timestamp.

        Callers block on the internal lock, so requests are serialised and
        released no faster than one per *min_interval* seconds.
        """
        async with self._lock:
            now = asyncio.get_running_loop().time()
            elapsed = now - self._last_call
            if elapsed < self.min_interval:
                # Pause for the remainder of the current window.
                await asyncio.sleep(self.min_interval - elapsed)
            self._last_call = asyncio.get_running_loop().time()


# ---------------------------------------------------------------------------
# NSE HTTP client
# ---------------------------------------------------------------------------

class NSEClient:
    """
    Async HTTP client tailored for the NSE India equity API.

    Handles:
    - **Concurrency control** via an asyncio ``Semaphore``.
    - **Rate limiting** via :class:`RateLimiter`.
    - **Cookie bootstrapping** — NSE requires a prior visit to the homepage
      so that session cookies are set before API calls are accepted.
    - **Retry with exponential back-off** and per-attempt jitter.
    - **403 recovery** — forces a cookie refresh when NSE blocks a request.
    """

    def __init__(
        self,
        max_concurrent: int = MAX_CONCURRENT,
        max_retries: int = MAX_RETRIES,
        min_interval: float = RATE_LIMIT_INTERVAL,
    ) -> None:
        """
        Args:
            max_concurrent: Maximum number of simultaneous in-flight requests.
            max_retries: How many times to attempt fetching a single symbol
                         before marking it as failed.
            min_interval: Minimum seconds between consecutive HTTP requests
                          (passed to :class:`RateLimiter`).
        """
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_retries = max_retries
        self.rate_limiter = RateLimiter(min_interval)

        # Cookie state shared across all concurrent fetch coroutines.
        self._cookie_lock = asyncio.Lock()
        self._cookie_refreshed = False

    async def _do_refresh(self, session: aiohttp.ClientSession, headers: dict) -> None:
        """
        Perform a GET to the NSE homepage so the session acquires fresh cookies.

        The response body is intentionally discarded; only the ``Set-Cookie``
        headers matter here.

        Args:
            session: The active aiohttp session whose cookie jar will be updated.
            headers: Request headers to include in the refresh call.
        """
        async with session.get(NSE_BASE_URL, headers=headers) as _:
            pass  # Response body is not needed; only the cookies matter.

    async def refresh_cookies(self, session: aiohttp.ClientSession, headers: dict) -> None:
        """
        Ensure session cookies are refreshed exactly once (lazily on first call).

        The ``_cookie_lock`` prevents multiple concurrent coroutines from all
        hitting the homepage simultaneously at startup. If cookies have already
        been refreshed, this method returns immediately.

        Args:
            session: The active aiohttp session to refresh cookies for.
            headers: Request headers to include in the refresh call.
        """
        async with self._cookie_lock:
            if self._cookie_refreshed:
                return  # Another coroutine already refreshed — nothing to do.
            await self._do_refresh(session, headers)
            self._cookie_refreshed = True

    async def fetch_one(
        self,
        session: aiohttp.ClientSession,
        symbol: str,
        manager: ResultManager,
    ) -> None:
        """
        Fetch market data for a single equity symbol and record the result.

        Retries up to :attr:`max_retries` times using exponential back-off
        with uniform jitter. A 403 response triggers an immediate cookie
        refresh before the next attempt. All other non-200 responses and
        network errors are logged and retried similarly.

        Args:
            session: Shared aiohttp ``ClientSession`` for the entire run.
            symbol: NSE stock symbol to fetch (e.g. ``"INFY"``).
            manager: :class:`ResultManager` instance used to record and persist
                     the outcome.
        """
        headers = get_headers(symbol)

        for attempt in range(self.max_retries):
            # Bootstrap session cookies on the very first attempt only.
            if attempt == 0:
                await self.refresh_cookies(session, headers)

            # Respect the global rate limit before acquiring the concurrency slot.
            await self.rate_limiter.acquire()

            async with self.semaphore:
                try:
                    print(f"Fetching {symbol} (Attempt {attempt + 1}/{self.max_retries})...")

                    url = f"{MARKET_DATA_URL}{symbol}"

                    async with session.get(
                        url,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(
                            connect=2,    # seconds to establish TCP connection
                            sock_read=3,  # seconds to read the response body
                            total=10,     # hard wall-clock cap for the full request
                        ),
                    ) as response:

                        if response.status == 200:
                            data = await response.json()
                            manager.update(symbol, data)
                            return  # Success — no further retries needed.

                        elif response.status == 403:
                            # NSE blocked the request; force a cookie refresh
                            # so the next attempt starts with a fresh session.
                            print(
                                f"[403] {symbol} blocked. "
                                f"Refreshing cookies (Attempt {attempt + 1}/{self.max_retries})..."
                            )
                            async with self._cookie_lock:
                                self._cookie_refreshed = False  # Invalidate cached state.
                                await self._do_refresh(session, headers)
                                self._cookie_refreshed = True

                        else:
                            print(f"Error fetching {symbol}: HTTP {response.status}")

                except asyncio.TimeoutError:
                    print(f"[Timeout] {symbol} attempt {attempt + 1}/{self.max_retries}")

                except aiohttp.ClientError as e:
                    print(f"[ClientError] {symbol}: {e} (Attempt {attempt + 1}/{self.max_retries})")

                except Exception as e:
                    print(f"[Exception] {symbol}: {e} (Attempt {attempt + 1}/{self.max_retries})")

            # Wait before the next attempt using exponential back-off + jitter.
            if attempt < self.max_retries - 1:
                sleep_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"Retrying {symbol} in {sleep_time:.2f} seconds...")
                await asyncio.sleep(sleep_time)

        # All attempts exhausted — record as a permanent failure.
        print(f"[Failed] {symbol} after {self.max_retries} attempts.")
        manager.update(symbol, None)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def fetch_market_data(symbols: List[str], output_dir: Path) -> None:
    """
    Concurrently fetch equity market data for every symbol in *symbols*.

    Creates a single shared :class:`aiohttp.ClientSession` and dispatches one
    coroutine per symbol. All coroutines run concurrently (bounded by the
    semaphore inside :class:`NSEClient`). A run summary is printed on completion.

    Args:
        symbols: List of NSE stock symbols to fetch.
        output_dir: Directory where successful JSON responses will be saved.
    """
    nse_client = NSEClient()
    manager = ResultManager(output_dir)

    async with aiohttp.ClientSession() as session:
        tasks = [nse_client.fetch_one(session, symbol, manager) for symbol in symbols]
        await asyncio.gather(*tasks)

    manager.report()


def run(symbols: List[str], output_dir: Path) -> None:
    """
    Synchronous entry point for fetching market data.

    Wraps :func:`fetch_market_data` in ``asyncio.run`` so it can be called
    from synchronous code or a script's ``__main__`` block.

    Args:
        symbols: List of NSE stock symbols to fetch.
        output_dir: Directory where successful JSON responses will be saved.
    """
    asyncio.run(fetch_market_data(symbols, output_dir))


if __name__ == "__main__":
    # ---------------------------------------------------------------------------
    # Quick smoke-test: fetch data for the first N Nifty 500 constituents.
    # ---------------------------------------------------------------------------
    import argparse
    import pandas as pd

    parser = argparse.ArgumentParser(description="Fetch NSE market data for Nifty 500 constituents.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory where fetched JSON files will be saved (default: %(default)s)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of symbols to fetch for a quick test run (default: %(default)s)",
    )
    args = parser.parse_args()

    # Official NSE CSV listing all Nifty 500 constituents.
    NIFTY500_URL = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"

    df = pd.read_csv(NIFTY500_URL)
    print(f"Fetched {len(df)} symbols from NSE India.")

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Limit to N symbols for a quick trial run.
    if args.limit > 0:
        N = min(args.limit, len(df))
        print(f"Limiting to the first {N} symbols for this run.")
    run(df.Symbol.tolist()[:N], output_dir)