import json
import random
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from typing import List, Optional


NSE_BASE_URL = "https://www.nseindia.com"
MARKET_DATA_URL = "https://www.nseindia.com/api/quote-equity?symbol="
REFERER_URL = "https://www.nseindia.com/get-quotes/equity?symbol="

BASE_HEADER = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}
MAX_RETRIES = 3
MAX_CONCURRENT = 3
BASE_DELAY_MIN = 1
BASE_DELAY_MAX = 4
OUTPUT_DIR = Path("data")


class ResultAggregator:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "empty": 0
        }
    
    async def update(self, symbol: str, result: Optional[dict]) -> None:
        self.stats["total"] += 1
        if result is None:
            self.stats["failed"] += 1
        elif not result:
            self.stats["empty"] += 1
        else:
            self.stats["success"] += 1
            await save_to_file(symbol, result, self.output_dir)
    
    def report(self) -> None:
        print(f"Total: {self.stats['total']}, Success: {self.stats['success']}, Failed: {self.stats['failed']}, Empty: {self.stats['empty']}")


def get_headers(symbol: str) -> dict[str, str]:
    """
    Generate headers for the HTTP request to NSE API for a given symbol.

    Args:
        symbol (str): The stock symbol for which to generate headers.

    Returns:
        dict[str, str]: A dictionary containing the headers for the request.
    """
    return {
        **BASE_HEADER,
        "Referer": f"{REFERER_URL}{symbol}",
    }

class NSEClient:
    def __init__(self, max_concurrent: int = MAX_CONCURRENT, max_retries: int = MAX_RETRIES) -> None:
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_retries = max_retries

    async def refresh_cookies(self, session, headers) -> None:
        try:
            async with session.get(NSE_BASE_URL, headers=headers) as _:
                pass  # Just to refresh cookies
        except Exception as e:
            print(f"Error refreshing cookies: {e}")

    async def fetch_one(self, session, symbol, aggregator: ResultAggregator) -> None:
        headers = get_headers(symbol)
        async with self.semaphore:
            for attempt in range(self.max_retries):
                try:
                    delay = random.uniform(BASE_DELAY_MIN, BASE_DELAY_MAX)
                    print(f"Fetching {symbol} (Attempt {attempt + 1}/{self.max_retries}) with delay {delay:.2f} seconds...")
                    
                    await asyncio.sleep(delay)  # Random delay to avoid rate limits
                    if attempt == 0:
                        await self.refresh_cookies(session, headers)
                    
                    url = f"{MARKET_DATA_URL}{symbol}"

                    async with session.get(
                        url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:

                        if response.status == 200:
                            data = await response.json()
                            await aggregator.update(symbol, data)
                            return
                        elif response.status == 403:
                            print(f"[403] {symbol} blocked. Refreshing cookies (Attempt {attempt + 1}/{self.max_retries})...")
                            await self.refresh_cookies(session, headers)
                        else:
                            print(f"Error fetching {symbol}: HTTP {response.status}")

                except asyncio.TimeoutError:
                    print(f"[Timeout] {symbol} attempt {attempt + 1}/{self.max_retries}")
                
                except aiohttp.ClientError as e:
                    print(f"[ClientError] {symbol}: {e} (Attempt {attempt + 1}/{self.max_retries})")
                
                except ValueError as e:
                    print(f"[DataError] {symbol}: {e} (Attempt {attempt + 1}/{self.max_retries})")

                sleep_time = (2 ** attempt) + random.uniform(0, 1)  # Exponential backoff with jitter
                print(f"Retrying {symbol} in {sleep_time:.2f} seconds...")
                await asyncio.sleep(sleep_time)

        print(f"[Failed] {symbol} after {self.max_retries} attempts.")
        await aggregator.update(symbol, None)  # Mark as failed after max retries

async def save_to_file(symbol: str, data: dict, output_dir: Path) -> None:
    output_file = output_dir / f"{symbol}.json"
    async with aiofiles.open(output_file, "w") as f:
        await f.write(json.dumps(data, indent=4))
    
async def fetch_market_data(symbols: List[str], output_dir: Path) -> None:
    nse_client = NSEClient()
    aggregator = ResultAggregator(output_dir)

    async with aiohttp.ClientSession() as session:
        tasks = [nse_client.fetch_one(session, symbol, aggregator) for symbol in symbols]
        await asyncio.gather(*tasks)
        aggregator.report()

def run(symbols: List[str], output_dir: Path) -> None:
    asyncio.run(fetch_market_data(symbols, output_dir))


if __name__ == "__main__":
    import pandas as pd

    NIFTY500_URL = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"

    df = pd.read_csv(NIFTY500_URL)

    print(f"Fetched {len(df)} symbols from NSE India.")
    
    output_dir = Path("experiments/exp_001_nifty_500_metadata/data")
    output_dir.mkdir(parents=True, exist_ok=True)

    run(df.Symbol.tolist()[:5], output_dir)