"""
AirDNA per-listing rentalizer scraper using Playwright.

Connects to an already-open Chrome browser via CDP (Chrome DevTools Protocol),
navigates to AirDNA rentalizer pages for individual Airbnb listings, and
extracts property metrics (Revenue, ADR, Occupancy, Bedrooms, Bathrooms,
Max Guests, Days Available, Rating, Review Count).
"""

import json
import logging
import os
import random
import re
import sys
import time

from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

AIRDNA_RENTALIZER_URL = "https://app.airdna.co/data/rentalizer"
PAGE_LOAD_WAIT_SECONDS = 5

# Label-to-field mapping for KPI cards on the rentalizer page
KPI_LABEL_MAP = {
    "annual revenue": "Revenue",
    "average daily rate": "ADR",
    "occupancy": "Occupancy",
    "days available": "Days_Available",
    "revenue potential": None,  # Not mapped to comp set schema
}


class AirDNAScraper:
    """Scrapes AirDNA rentalizer pages for per-listing property metrics.

    Connects to a running Chrome instance via CDP remote debugging,
    navigates to rentalizer URLs for each listing ID, and extracts
    Revenue, ADR, Occupancy, Bedrooms, Bathrooms, Max Guests,
    Days Available, Rating, and Review Count.

    Args:
        cdp_url: Chrome DevTools Protocol URL (e.g. http://localhost:9222).
        listing_ids: List of Airbnb listing IDs to look up.
        inspect_mode: When True, pauses after navigation for selector discovery.
        min_days_available: Minimum Days Available to include a listing (default 100).
    """

    def __init__(
        self,
        cdp_url: str,
        listing_ids: list[str],
        inspect_mode: bool = False,
        min_days_available: int = 100,
    ) -> None:
        self.cdp_url = cdp_url
        self.listing_ids = listing_ids
        self.inspect_mode = inspect_mode
        self.min_days_available = min_days_available

    def _build_rentalizer_url(self, listing_id: str) -> str:
        """Build the AirDNA rentalizer URL for a single listing.

        Args:
            listing_id: The Airbnb listing ID.

        Returns:
            Full URL string for the rentalizer page.
        """
        return f"{AIRDNA_RENTALIZER_URL}?&listing_id=abnb_{listing_id}"

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

    def should_include_listing(self, metrics: dict) -> bool:
        """Check if a listing meets the minimum Days Available threshold.

        Args:
            metrics: Dict with at least a 'Days_Available' key.

        Returns:
            True if the listing should be included, False otherwise.
        """
        return metrics.get("Days_Available", 0) >= self.min_days_available

    def _extract_header_metrics(self, page) -> dict:
        """Extract Bedrooms, Bathrooms, Max Guests, Rating, Review Count from header.

        The rentalizer page header shows icon+text pairs like:
          bed icon 4  |  bath icon 3  |  person icon 15  |  star 4.7 (287)

        Args:
            page: Playwright page object.

        Returns:
            Dict with Bedrooms, Bathrooms, Max_Guests, Rating, Review_Count.
        """
        metrics = {
            "Bedrooms": 0,
            "Bathrooms": 0.0,
            "Max_Guests": 0,
            "Rating": 0.0,
            "Review_Count": 0,
        }

        # Look for the header stats area — icons followed by numbers
        # The page shows bed/bath/guest counts and star rating near the title
        try:
            # Try to find the stats container with bed/bath/guest/rating info
            header_text = page.locator("h1").first.evaluate(
                """el => {
                    // Get the parent container's text for the stats row
                    let parent = el.parentElement;
                    return parent ? parent.innerText : '';
                }"""
            )

            # Parse bedrooms (bed icon followed by number)
            bed_match = re.search(
                r"(\d+)\s*$", header_text.split("\n")[0] if header_text else ""
            )

            # Alternative: look for specific stat elements
            stat_elements = page.locator(
                "[class*='stat'], [class*='detail'], [class*='overview'] span, [class*='overview'] div"
            ).all()
            stat_texts = []
            for el in stat_elements:
                try:
                    text = el.inner_text().strip()
                    if text:
                        stat_texts.append(text)
                except Exception:
                    pass

            logger.debug(f"Header stat texts: {stat_texts}")
        except Exception as e:
            logger.debug(f"Could not extract header stats via class selectors: {e}")

        # Fallback: extract from the whole page text near the title
        try:
            # Look for rating pattern like "4.7 (287)" or "★ 4.7 (287)"
            page_text = page.locator("body").inner_text()
            rating_match = re.search(r"★?\s*([\d.]+)\s*\((\d+)\)", page_text)
            if rating_match:
                metrics["Rating"] = float(rating_match.group(1))
                metrics["Review_Count"] = int(rating_match.group(2))

            # Look for bed/bath/guest counts near "Short-term Rental"
            # Format from screenshot: bed_icon 4  bath_icon 3  person_icon 15
            header_section = page_text[:500]  # Header is near the top

            # Find sequences of small numbers that represent bed/bath/guests
            bed_match = re.search(
                r"(?:bed|bedroom)s?\s*[:.]?\s*(\d+)", header_section, re.IGNORECASE
            )
            if bed_match:
                metrics["Bedrooms"] = int(bed_match.group(1))

            bath_match = re.search(
                r"(?:bath|bathroom)s?\s*[:.]?\s*(\d+\.?\d*)",
                header_section,
                re.IGNORECASE,
            )
            if bath_match:
                metrics["Bathrooms"] = float(bath_match.group(1))

            guest_match = re.search(
                r"(?:guest|max.?guest)s?\s*[:.]?\s*(\d+)", header_section, re.IGNORECASE
            )
            if guest_match:
                metrics["Max_Guests"] = int(guest_match.group(1))

        except Exception as e:
            logger.warning(f"Error extracting header metrics: {e}")

        return metrics

    def _extract_kpi_metrics(self, page) -> dict:
        """Extract KPI card values from the rentalizer page.

        The page shows cards with:
          Revenue Potential | Days Available | Annual Revenue | Occupancy | Average Daily Rate

        Args:
            page: Playwright page object.

        Returns:
            Dict with Revenue, ADR, Occupancy, Days_Available.
        """
        metrics = {
            "Revenue": 0.0,
            "ADR": 0.0,
            "Occupancy": 0,
            "Days_Available": 0,
        }

        try:
            # Get all text content and look for KPI patterns
            page_text = page.locator("body").inner_text()

            # Look for "Annual Revenue" followed by a dollar value
            revenue_match = re.search(
                r"([\$\d,.]+[KkMm]?)\s*\n?\s*Annual Revenue",
                page_text,
            )
            if revenue_match:
                metrics["Revenue"] = self._parse_revenue(revenue_match.group(1))

            # Look for "Average Daily Rate" with dollar value
            adr_match = re.search(
                r"([\$\d,.]+)\s*\n?\s*Average Daily Rate",
                page_text,
            )
            if adr_match:
                metrics["ADR"] = self._parse_currency(adr_match.group(1))

            # Look for "Occupancy" with percentage
            occ_match = re.search(
                r"(\d+%?)\s*\n?\s*Occupancy",
                page_text,
            )
            if occ_match:
                metrics["Occupancy"] = self._parse_percentage(occ_match.group(1))

            # Look for "Days Available" with number
            days_match = re.search(
                r"(\d+)\s*\n?\s*Days Available",
                page_text,
            )
            if days_match:
                metrics["Days_Available"] = self._parse_days(days_match.group(1))

        except Exception as e:
            logger.warning(f"Error extracting KPI metrics: {e}")

        return metrics

    def scrape_listing(self, page, listing_id: str) -> dict:
        """Scrape property metrics from a single rentalizer page.

        Args:
            page: Playwright page object.
            listing_id: The Airbnb listing ID.

        Returns:
            Dict with all property metrics.
        """
        url = self._build_rentalizer_url(listing_id)
        logger.info(f"Navigating to listing: {url}")
        page.goto(url, wait_until="domcontentloaded")

        # Wait for KPI content to appear
        try:
            page.wait_for_selector(
                "text=Annual Revenue", state="visible", timeout=30_000
            )
            logger.info(f"Rentalizer page loaded for listing {listing_id}.")
        except Exception:
            logger.warning(
                f"KPI content not found within 30s for listing {listing_id}. "
                "Page may not have loaded correctly."
            )

        if self.inspect_mode:
            logger.info(
                "Inspect mode enabled. Use Playwright Inspector to find selectors."
            )
            logger.info("Close the inspector or press 'Resume' to continue.")
            page.pause()

        page.wait_for_timeout(int(PAGE_LOAD_WAIT_SECONDS * 1000))

        # Extract all metrics from the page
        header_metrics = self._extract_header_metrics(page)
        kpi_metrics = self._extract_kpi_metrics(page)

        metrics = {
            "ADR": kpi_metrics.get("ADR", 0.0),
            "Occupancy": kpi_metrics.get("Occupancy", 0),
            "Revenue": kpi_metrics.get("Revenue", 0.0),
            "Bedrooms": header_metrics.get("Bedrooms", 0),
            "Bathrooms": header_metrics.get("Bathrooms", 0.0),
            "Max_Guests": header_metrics.get("Max_Guests", 0),
            "Days_Available": kpi_metrics.get("Days_Available", 0),
            "LY_Revenue": 0.0,
            "Rating": header_metrics.get("Rating", 0.0),
            "Review_Count": header_metrics.get("Review_Count", 0),
        }

        return metrics

    def save_listing_result(
        self,
        listing_id: str,
        data: dict,
        output_dir: str = "outputs/02_comp_sets",
    ) -> None:
        """Save scraped data for a single listing to a JSON file.

        Args:
            listing_id: The Airbnb listing ID (used in filename).
            data: Dict of metric values for this listing.
            output_dir: Directory to write the output file to.
        """
        os.makedirs(output_dir, exist_ok=True)
        filename = f"listing_{listing_id}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({listing_id: data}, f, indent=4)

        logger.info(f"Saved listing {listing_id} to {filepath}")

    def run(self) -> None:
        """Execute the full scraping workflow.

        Connects to Chrome via CDP, iterates over listing IDs,
        scrapes each one from the rentalizer page, filters by
        min_days_available, and saves results to per-listing JSON files.
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

            scraped = 0
            filtered = 0

            for listing_id in self.listing_ids:
                logger.info(f"Scraping listing: {listing_id}")
                metrics = self.scrape_listing(page, listing_id)

                if self.should_include_listing(metrics):
                    self.save_listing_result(listing_id, metrics)
                    scraped += 1
                else:
                    logger.info(
                        f"Skipping listing {listing_id}: "
                        f"Days_Available={metrics.get('Days_Available', 0)} "
                        f"< {self.min_days_available}"
                    )
                    filtered += 1

                # Rate limiting between requests
                time.sleep(random.uniform(2, 5))

            page.close()

        logger.info(
            f"AirDNA scraping complete. Saved {scraped} listings, filtered {filtered}."
        )


if __name__ == "__main__":
    import json as json_mod

    with open("config.json", "r") as f:
        config = json_mod.load(f)

    # Load listing IDs from search results
    zipcode = config.get("zipcode", "97067")
    search_results_path = f"outputs/01_search_results/search_results_{zipcode}.json"

    if os.path.isfile(search_results_path):
        with open(search_results_path, "r", encoding="utf-8") as f:
            search_results = json_mod.load(f)
        ids = [str(r.get("room_id", r.get("id", ""))) for r in search_results]
        ids = [i for i in ids if i]
    else:
        logger.error(
            f"No search results found at {search_results_path}. Run search first."
        )
        sys.exit(1)

    scraper = AirDNAScraper(
        cdp_url=config.get("airdna_cdp_url", "http://localhost:9222"),
        listing_ids=ids,
        inspect_mode=config.get("airdna_inspect_mode", False),
        min_days_available=config.get("min_days_available", 100),
    )
    scraper.run()
