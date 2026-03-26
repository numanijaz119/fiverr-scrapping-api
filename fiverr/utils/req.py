import re

import requests
from bs4 import BeautifulSoup

from fiverr.utils.scrape_utils import get_perseus_initial_props

SCRAPER_API_URL = "https://api.scraperapi.com/"
SCRAPER_API_REF = "https://www.scraperapi.com/?fp_ref=enable-fiverr-api"


# ---------------------------------------------------------------------------
# ScraperAPI-specific exceptions
# ---------------------------------------------------------------------------

class ScraperApiError(Exception):
    """Base class for ScraperAPI errors."""

class ScraperApiKeyError(ScraperApiError):
    """Raised when the API key is missing, invalid, or the account is suspended."""

class ScraperApiQuotaError(ScraperApiError):
    """Raised when the monthly request quota has been exhausted."""


# Body fragments ScraperAPI returns on various error conditions
_QUOTA_PHRASES = [
    "exceeded your monthly api call limit",
    "exceeded your monthly limit",
    "you have used all",
    "request limit reached",
    "concurrent request limit",
]
_KEY_PHRASES = [
    "invalid api key",
    "api key is not valid",
    "unauthorized",
    "account suspended",
    "account is banned",
]


def _check_scraper_api_response(response: 'requests.Response'):
    """
    Inspect the ScraperAPI response and raise a descriptive exception when
    an API-level error is detected (not a Fiverr-side error).
    """
    status = response.status_code
    body   = response.text.lower()

    if status == 401 or any(p in body for p in _KEY_PHRASES):
        raise ScraperApiKeyError(
            "ScraperAPI key is invalid or the account is suspended. "
            "Check your key in Settings."
        )

    if status == 403 or any(p in body for p in _QUOTA_PHRASES):
        raise ScraperApiQuotaError(
            "ScraperAPI monthly quota has been used up. "
            "Upgrade your plan or wait for the next billing cycle."
        )

    if status == 429:
        raise ScraperApiError(
            "ScraperAPI rate limit hit (too many concurrent requests). "
            "Try increasing the delay between requests."
        )


class Response(requests.Response):
    soup: 'BeautifulSoup'

    def set_soup(self):
        self.soup = BeautifulSoup(self.text, 'html5lib')

    def props_json(self) -> dict:
        return get_perseus_initial_props(self.soup)


class Session(requests.Session):
    def __init__(self):
        super().__init__()
        self.SCRAPER_API_KEY = None
        self.USE_SCRAPER_API = True
        self.country_code = "us"
        self.device_type = "desktop"
        self.session_number = 1

    def request(
            self,
            method,
            url: str = '',
            self_: 'Session' = None,
            *args,
            **kwargs,
    ) -> Response:
        if not re.match(r"https://(www\.)?fiverr\.com/", url):
            raise ValueError(
                f"Invalid URL: {url}, must be a Fiverr URL.")
        if self_ is None:
            self_ = self
        if self_.USE_SCRAPER_API and not self_.SCRAPER_API_KEY:
            raise ValueError(
                f"No Scraper API key found, please get one from {SCRAPER_API_REF}, and "
                f"use `set_scraper_api_key(` to set it.")
        if self_.SCRAPER_API_KEY and self_.USE_SCRAPER_API:
            kwargs["params"] = {
                "api_key": self_.SCRAPER_API_KEY,
                "url": url,
                "country_code": self_.country_code,
                "device_type": self_.device_type,
                "session_number": self_.session_number,
            }
            url = SCRAPER_API_URL
        response = super().request(method, url, *args, **kwargs)
        _check_scraper_api_response(response)
        response.__class__ = Response
        response.set_soup()
        return response

    def set_scraper_api_key(self, api_key: str):
        self.SCRAPER_API_KEY = api_key

    def set_session_number(self, session_number: int):
        self.session_number = session_number


session = Session()
