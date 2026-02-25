"""
AirDNA comp set scraper using Playwright.

Connects to an already-open Chrome browser via CDP (Chrome DevTools Protocol),
navigates to AirDNA comp set pages, handles infinite scroll, and extracts
property metrics (Airbnb listing ID, Revenue, ADR, Occupancy, Bedrooms,
Bathrooms).
"""

import json
import logging
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

AIRDNA_BASE_URL = "https://app.airdna.co/data/comp-sets"
SCROLL_PAUSE_SECONDS = 2.0
SCROLL_MAX_RETRIES = 5
PAGE_LOAD_WAIT_SECONDS = 5


class AirDNAScraper:
    """Scrapes AirDNA comp set pages for property metrics.

    Connects to a running Chrome instance via CDP remote debugging,
    navigates to comp set URLs, scrolls through infinite-scroll listings,
    and extracts Revenue, ADR, Occupancy, Bedrooms, and Bathrooms per property.

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

    def _parse_revenue(self, value: str) -> float:
        """Parse a revenue string like '$47.8K' or '$174.9K' to a float.

        Args:
            value: String like '$47.8K', '$1.2M', or '$47800'.

        Returns:
            Numeric value as float.
        """
        cleaned = value.replace("$", "").replace(",", "").strip()
        multiplier = 1.0
        if cleaned.upper().endswith("K"):
            multiplier = 1_000
            cleaned = cleaned[:-1]
        elif cleaned.upper().endswith("M"):
            multiplier = 1_000_000
            cleaned = cleaned[:-1]
        return float(cleaned) * multiplier

    def _parse_bedrooms(self, value: str) -> float:
        """Parse a bedrooms/bathrooms value that may be a decimal.

        Args:
            value: String like '3', '2.5', or '4'.

        Returns:
            Numeric value as float.
        """
        return float(value.strip())

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

    def _find_scroll_container(self, page):
        """Find the scrollable container for the comp set list.

        The AirDNA page has the property list in a scrollable panel,
        not the document body. This method finds that container.

        Args:
            page: Playwright page object.

        Returns:
            Playwright element handle for the scrollable container,
            or None if not found (falls back to body scroll).
        """
        candidates = [
            "div[class*='comp-set']",
            "div[class*='compset']",
            "div[class*='listing']",
            "div[class*='table-container']",
            "div[class*='scroll']",
        ]
        for selector in candidates:
            el = page.query_selector(selector)
            if el:
                logger.info(f"Found scroll container: {selector}")
                return el

        # Fallback: find the element containing the table that has overflow scroll
        container = page.evaluate("""() => {
            const tables = document.querySelectorAll('table');
            for (const table of tables) {
                let el = table.parentElement;
                while (el && el !== document.body) {
                    const style = window.getComputedStyle(el);
                    if (style.overflowY === 'auto' || style.overflowY === 'scroll') {
                        return true;
                    }
                    el = el.parentElement;
                }
            }
            return false;
        }""")

        if container:
            # Use JS-based scrolling for the detected container
            logger.info("Found scrollable parent via computed style.")
            return None  # Will use JS-based approach in _scroll_to_bottom

        logger.info("No scroll container found, will scroll document body.")
        return None

    def _scroll_to_bottom(self, page) -> None:
        """Scroll the page to load all infinite-scroll content.

        Tries to scroll the specific comp set container first. If no
        scrollable container is found, falls back to scrolling the
        document body and the first scrollable ancestor of the table.

        Args:
            page: Playwright page object.
        """
        previous_count = 0
        retry_count = 0

        while True:
            # Scroll both the body and any scrollable table ancestor
            page.evaluate("""() => {
                window.scrollTo(0, document.body.scrollHeight);
                const tables = document.querySelectorAll('table');
                for (const table of tables) {
                    let el = table.parentElement;
                    while (el && el !== document.body) {
                        const style = window.getComputedStyle(el);
                        if (style.overflowY === 'auto' || style.overflowY === 'scroll') {
                            el.scrollTop = el.scrollHeight;
                            break;
                        }
                        el = el.parentElement;
                    }
                }
            }""")
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

        AirDNA embeds listing images from muscache.com (Airbnb's CDN)
        with URLs like:
          https://a0.muscache.com/.../Hosting-1050769200886027711/original/...

        VRBO listings use a different CDN, so only muscache.com images
        indicate Airbnb listings. Returns None for non-Airbnb rows.

        Args:
            row: Playwright element handle for a table row.

        Returns:
            Listing ID string for Airbnb listings, or None if not found
            or not an Airbnb listing.
        """
        # Primary: extract from Airbnb image URL (muscache.com CDN)
        images = row.query_selector_all("img")
        for img in images:
            src = img.get_attribute("src") or ""
            if "muscache.com" in src:
                match = re.search(r"Hosting-(\d+)", src)
                if match:
                    return match.group(1)

        # Fallback: links containing airbnb.com/rooms/
        links = row.query_selector_all("a[href]")
        for link in links:
            href = link.get_attribute("href") or ""
            match = re.search(r"airbnb\.com/rooms/(\d+)", href)
            if match:
                return match.group(1)
            # AirDNA internal links with listing_id=abnb_{id}
            match = re.search(r"listing_id=abnb_(\d+)", href)
            if match:
                return match.group(1)

        return None

    def _extract_property_data(self, row) -> tuple[str | None, dict]:
        """Extract metrics from a single property row element.

        Known AirDNA comp set column order (indices):
          [0] Listing name
          [1] Revenue     ($132.8K)
          [2] ADR         ($969.19)
          [3] Occupancy   (42%)
          [4] Bedrooms    (6)
          [5] Bathrooms   (3.5)
          [6] Max Guests  (15)
          [7] Days Avail  (330)
          [8] LY Revenue  ($141.4K)
          [9] Rating      (4.8 (35))
          [10] (action)

        Args:
            row: Playwright element handle for a property row.

        Returns:
            Tuple of (listing_id, metrics_dict). listing_id may be None
            if extraction fails or the listing is not from Airbnb.
        """
        listing_id = self._extract_listing_id(row)

        cells = row.query_selector_all("td")
        metrics = {
            "ADR": 0.0,
            "Occupancy": 0,
            "Revenue": 0.0,
            "Bedrooms": 0,
            "Bathrooms": 0.0,
            "Max_Guests": 0,
            "Days_Available": 0,
            "LY_Revenue": 0.0,
            "Rating": 0.0,
            "Review_Count": 0,
        }

        cell_texts = [cell.inner_text().strip() for cell in cells]
        logger.debug(f"Row cells: {cell_texts}")

        if len(cell_texts) < 8:
            logger.warning(f"Row has only {len(cell_texts)} cells, expected 10+. Skipping.")
            return listing_id, metrics

        # Positional extraction based on known column order
        # [1] Revenue
        try:
            metrics["Revenue"] = self._parse_revenue(cell_texts[1])
        except (ValueError, IndexError):
            pass

        # [2] ADR
        try:
            metrics["ADR"] = self._parse_currency(cell_texts[2])
        except (ValueError, IndexError):
            pass

        # [3] Occupancy
        try:
            metrics["Occupancy"] = self._parse_percentage(cell_texts[3])
        except (ValueError, IndexError):
            pass

        # [4] Bedrooms
        try:
            metrics["Bedrooms"] = int(float(cell_texts[4]))
        except (ValueError, IndexError):
            pass

        # [5] Bathrooms
        try:
            metrics["Bathrooms"] = self._parse_bedrooms(cell_texts[5])
        except (ValueError, IndexError):
            pass

        # [6] Max Guests
        try:
            metrics["Max_Guests"] = int(cell_texts[6])
        except (ValueError, IndexError):
            pass

        # [7] Days Available
        try:
            metrics["Days_Available"] = self._parse_days(cell_texts[7])
        except (ValueError, IndexError):
            pass

        # [8] LY Revenue
        try:
            metrics["LY_Revenue"] = self._parse_revenue(cell_texts[8])
        except (ValueError, IndexError):
            pass

        # [9] Rating (format: "4.8 (35)" or "-- (0)")
        if len(cell_texts) > 9:
            rating_text = cell_texts[9]
            rating_match = re.match(r"([\d.]+)\s*\((\d+)\)", rating_text)
            if rating_match:
                try:
                    metrics["Rating"] = float(rating_match.group(1))
                    metrics["Review_Count"] = int(rating_match.group(2))
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
        page.goto(url, wait_until="domcontentloaded")

        # Wait for the table to appear rather than networkidle,
        # since the map tiles keep firing network requests forever.
        try:
            page.wait_for_selector(
                "table", state="attached", timeout=30_000
            )
            logger.info("Table element detected on page.")
        except Exception:
            logger.warning(
                "Table not found within 30s. Page may not have loaded correctly."
            )

        if self.inspect_mode:
            logger.info(
                "Inspect mode enabled. Use Playwright Inspector to find selectors."
            )
            logger.info("Close the inspector or press 'Resume' to continue.")
            page.pause()

        page.wait_for_timeout(int(PAGE_LOAD_WAIT_SECONDS * 1000))

        self._scroll_to_bottom(page)

        rows = page.query_selector_all("table tbody tr")
        if not rows:
            logger.warning(
                f"No property rows found for comp set {comp_set_id}. "
                "Run with inspect_mode=True to discover selectors."
            )
            return {}

        logger.info(f"Found {len(rows)} table rows. Extracting Airbnb listings...")
        results = {}
        skipped = 0

        for row in rows:
            listing_id, metrics = self._extract_property_data(row)
            if listing_id:
                results[listing_id] = metrics
            else:
                skipped += 1

        logger.info(
            f"Extracted {len(results)} Airbnb listings. "
            f"Skipped {skipped} rows (non-Airbnb or no listing ID)."
        )
        return results

    def save_results(
        self,
        comp_set_id: str,
        data: dict,
        output_dir: str = "property_comp_sets",
    ) -> None:
        """Save scraped data to a JSON file.

        Args:
            comp_set_id: The AirDNA comp set identifier (used in filename).
            data: Dict mapping listing ID strings to metric dicts.
            output_dir: Directory to write the output file to.
        """
        os.makedirs(output_dir, exist_ok=True)
        filename = f"compset_{comp_set_id}.json"
        filepath = os.path.join(output_dir, filename)

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
