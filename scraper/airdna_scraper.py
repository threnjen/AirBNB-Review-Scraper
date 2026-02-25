"""
AirDNA comp set scraper using Playwright.

Connects to an already-open Chrome browser via CDP (Chrome DevTools Protocol),
navigates to AirDNA comp set pages, handles infinite scroll, and extracts
property metrics (Airbnb listing ID, ADR, Occupancy, Days Available).
"""

import json
import logging
import re
import sys
import time

from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

AIRDNA_BASE_URL = "https://app.airdna.co/data/comp-sets"
SCROLL_PAUSE_SECONDS = 2.0
SCROLL_MAX_RETRIES = 5


class AirDNAScraper:
    """Scrapes AirDNA comp set pages for property metrics.

    Connects to a running Chrome instance via CDP remote debugging,
    navigates to comp set URLs, scrolls through infinite-scroll listings,
    and extracts ADR, Occupancy, and Days Available per property.

    Args:
        cdp_url: Chrome DevTools Protocol URL (e.g. http://localhost:9222).
        comp_set_ids: List of AirDNA comp set IDs to scrape.
        inspect_mode: When True, pauses after navigation for selector discovery.
    """

    def __init__(
        self,
        cdp_url: str,
        comp_set_ids: list[str],
        inspect_mode: bool = False,
    ) -> None:
        self.cdp_url = cdp_url
        self.comp_set_ids = comp_set_ids
        self.inspect_mode = inspect_mode

    def _build_comp_set_url(self, comp_set_id: str) -> str:
        """Build the full AirDNA comp set URL.

        Args:
            comp_set_id: The AirDNA comp set identifier.

        Returns:
            Full URL string for the comp set page.
        """
        return f"{AIRDNA_BASE_URL}/{comp_set_id}"

    def _parse_currency(self, value: str) -> float:
        """Parse a currency string to a float.

        Args:
            value: String like '$945.57' or '$1,234.56'.

        Returns:
            Numeric value as float.
        """
        cleaned = value.replace("$", "").replace(",", "").strip()
        return float(cleaned)

    def _parse_percentage(self, value: str) -> int:
        """Parse a percentage string to an integer.

        Args:
            value: String like '88%' or '88'.

        Returns:
            Numeric value as int.
        """
        cleaned = value.replace("%", "").strip()
        return int(float(cleaned))

    def _parse_days(self, value: str) -> int:
        """Parse a days available string to an integer.

        Args:
            value: String like '335' or '335 days'.

        Returns:
            Numeric value as int.
        """
        match = re.search(r"\d+", value)
        if match:
            return int(match.group())
        raise ValueError(f"Could not parse days from: {value}")

    def _should_continue_scrolling(
        self,
        previous_count: int,
        current_count: int,
        max_retries: int,
        retry_count: int,
    ) -> bool:
        """Determine whether to continue the infinite scroll loop.

        Args:
            previous_count: Number of property elements before last scroll.
            current_count: Number of property elements after last scroll.
            max_retries: Maximum consecutive scrolls with no new elements.
            retry_count: Current number of retries with no change.

        Returns:
            True if scrolling should continue, False if done.
        """
        if current_count > previous_count:
            return True
        return retry_count < max_retries

    def _scroll_to_bottom(self, page) -> None:
        """Scroll the page to load all infinite-scroll content.

        Repeatedly scrolls down and waits for new property elements to
        appear. Stops when element count stabilizes after max retries.

        Args:
            page: Playwright page object.
        """
        previous_count = 0
        retry_count = 0

        while True:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(SCROLL_PAUSE_SECONDS)

            current_count = len(page.query_selector_all("tr[data-testid]"))
            if current_count == 0:
                current_count = len(page.query_selector_all("table tbody tr"))

            if not self._should_continue_scrolling(
                previous_count, current_count, SCROLL_MAX_RETRIES, retry_count
            ):
                logger.info(
                    f"Scroll complete. Found {current_count} property elements."
                )
                break

            if current_count > previous_count:
                retry_count = 0
                logger.info(f"Scrolling... {current_count} properties loaded so far.")
            else:
                retry_count += 1
                logger.info(
                    f"No new elements. Retry {retry_count}/{SCROLL_MAX_RETRIES}."
                )

            previous_count = current_count

    def _extract_listing_id(self, row) -> str | None:
        """Extract the Airbnb listing ID from a table row element.

        Looks for links containing airbnb.com/rooms/ or data attributes
        containing the listing ID.

        Args:
            row: Playwright element handle for a table row.

        Returns:
            Listing ID string, or None if not found.
        """
        links = row.query_selector_all("a[href]")
        for link in links:
            href = link.get_attribute("href") or ""
            match = re.search(r"airbnb\.com/rooms/(\d+)", href)
            if match:
                return match.group(1)

        row_text = row.inner_text()
        data_id = row.get_attribute("data-testid") or ""
        id_match = re.search(r"(\d{6,})", data_id)
        if id_match:
            return id_match.group(1)

        return None

    def _extract_property_data(self, row) -> tuple[str | None, dict]:
        """Extract metrics from a single property row element.

        Args:
            row: Playwright element handle for a property row.

        Returns:
            Tuple of (listing_id, metrics_dict). listing_id may be None
            if extraction fails. metrics_dict has ADR, Occupancy,
            Days_Available keys.
        """
        listing_id = self._extract_listing_id(row)

        cells = row.query_selector_all("td")
        metrics = {"ADR": 0.0, "Occupancy": 0, "Days_Available": 0}

        cell_texts = [cell.inner_text().strip() for cell in cells]
        logger.info(f"Row cells: {cell_texts}")

        for text in cell_texts:
            if "$" in text:
                try:
                    metrics["ADR"] = self._parse_currency(text)
                except (ValueError, IndexError):
                    pass
            elif "%" in text:
                try:
                    metrics["Occupancy"] = self._parse_percentage(text)
                except (ValueError, IndexError):
                    pass

        for text in cell_texts:
            if text.isdigit() and 1 <= int(text) <= 365:
                try:
                    metrics["Days_Available"] = self._parse_days(text)
                except ValueError:
                    pass

        return listing_id, metrics

    def scrape_comp_set(self, page, comp_set_id: str) -> dict:
        """Scrape all property data from a single comp set page.

        Args:
            page: Playwright page object.
            comp_set_id: The AirDNA comp set identifier.

        Returns:
            Dict mapping listing ID strings to metric dicts.
        """
        url = self._build_comp_set_url(comp_set_id)
        logger.info(f"Navigating to comp set: {url}")
        page.goto(url, wait_until="networkidle")

        if self.inspect_mode:
            logger.info(
                "Inspect mode enabled. Use Playwright Inspector to find selectors."
            )
            logger.info("Close the inspector or press 'Resume' to continue.")
            page.pause()

        page.wait_for_timeout(3000)

        self._scroll_to_bottom(page)

        rows = page.query_selector_all("tr[data-testid]")
        if not rows:
            rows = page.query_selector_all("table tbody tr")
        if not rows:
            logger.warning(
                f"No property rows found for comp set {comp_set_id}. "
                "Run with inspect_mode=True to discover selectors."
            )
            return {}

        logger.info(f"Extracting data from {len(rows)} property rows.")
        results = {}
        skipped = 0

        for row in rows:
            listing_id, metrics = self._extract_property_data(row)
            if listing_id:
                results[listing_id] = metrics
            else:
                skipped += 1

        logger.info(
            f"Extracted {len(results)} listings. Skipped {skipped} rows (no listing ID found)."
        )
        return results

    def save_results(
        self,
        comp_set_id: str,
        data: dict,
        output_dir: str = ".",
    ) -> None:
        """Save scraped data to a JSON file.

        Args:
            comp_set_id: The AirDNA comp set identifier (used in filename).
            data: Dict mapping listing ID strings to metric dicts.
            output_dir: Directory to write the output file to.
        """
        filename = f"compset_{comp_set_id}.json"
        filepath = f"{output_dir}/{filename}"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        logger.info(f"Saved {len(data)} listings to {filepath}")

    def run(self) -> None:
        """Execute the full scraping workflow.

        Connects to Chrome via CDP, iterates over comp set IDs,
        scrapes each one, and saves results to JSON files.
        """
        logger.info(f"Connecting to Chrome at {self.cdp_url}")

        with sync_playwright() as pw:
            try:
                browser = pw.chromium.connect_over_cdp(self.cdp_url)
            except Exception as e:
                logger.error(
                    f"Failed to connect to Chrome at {self.cdp_url}. "
                    f"Launch Chrome with: open -a 'Google Chrome' "
                    f"--args --remote-debugging-port=9222\n"
                    f"Error: {e}"
                )
                raise ConnectionError(
                    f"Could not connect to Chrome at {self.cdp_url}. "
                    "Is Chrome running with --remote-debugging-port=9222?"
                ) from e

            contexts = browser.contexts
            if not contexts:
                logger.error(
                    "No browser contexts found. Open a Chrome window and "
                    "log into AirDNA before running the scraper."
                )
                raise RuntimeError("No browser contexts available in Chrome.")

            context = contexts[0]
            page = context.new_page()

            for comp_set_id in self.comp_set_ids:
                logger.info(f"Scraping comp set: {comp_set_id}")
                data = self.scrape_comp_set(page, comp_set_id)
                self.save_results(comp_set_id, data)

            page.close()

        logger.info("AirDNA scraping complete.")


if __name__ == "__main__":
    import json as json_mod

    with open("config.json", "r") as f:
        config = json_mod.load(f)

    scraper = AirDNAScraper(
        cdp_url=config.get("airdna_cdp_url", "http://localhost:9222"),
        comp_set_ids=config.get("airdna_comp_set_ids", []),
        inspect_mode=config.get("airdna_inspect_mode", False),
    )
    scraper.run()
