# Saaransh data platform

This repo contains the code for downloading and parsing the Nifty 500 company names and their metadata from National Stock Exchange.

## Some features of the code:
1. Getting cookies from NSE website before making API calls
2. Multiple async calls to NSE API
3. Enforces a minimum interval between consecutive acquisitions using rate limiter.
4. Refresh cookies when 403 status
5. Retries with exponential back-off with jitter
6. Parsing important data from NSE json dataand saving to a disk

## Run locally
```
uv run src/data_source/nse/scraper.py --limit 10 # Fetches 10 company metadata
uv run src/data_source/nse/scraper.py # Fetches all 500 company metadata
```

## To do:
1. Add logging
2. Make it API based
3. Monitoring
4. Error codes
5. Job Persistence
6. Data versioning
7. Storage class for S3 and MinIO