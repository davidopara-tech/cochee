"""Fetches raw data from the FPL public API."""

import time
import requests

BASE_URL = "https://fantasy.premierleague.com/api"

HEADERS = {
    "User-Agent": "Cochee-FPL-Agent/0.1 (hackathon project)",
    "Accept": "application/json",
}

TIMEOUT = (5, 15)
MAX_RETRIES = 3


def _get(path: str) -> dict | list:
    """GET a path from FPL, retrying on rate limit or server errors."""
    url = f"{BASE_URL}{path}"

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        except requests.RequestException:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)
            continue

        # Retry only on rate limits and server errors.
        if response.status_code == 429 or 500 <= response.status_code < 600:
            if attempt == MAX_RETRIES - 1:
                response.raise_for_status()
            time.sleep(2 ** attempt)
            continue

        response.raise_for_status()
        return response.json()


def fetch_bootstrap() -> dict:
    """Returns players, teams, and gameweeks for the current season."""
    return _get("/bootstrap-static/")


def fetch_fixtures() -> list:
    """Returns every fixture for the season."""
    return _get("/fixtures/")