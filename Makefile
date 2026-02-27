# Makefile for setting up the environment and running the AirBNB Review Scraper project

# Variables
PIPENV := pipenv
PYTHON := $(PIPENV) run python
PYTEST := $(PIPENV) run pytest
OS := $(shell uname)

# Default target
default: help

# Help target
help:
	@echo "Available targets:"
	@echo "  setup          - Install dependencies and Playwright browsers"
	@echo "  test           - Run all tests with coverage"
	@echo "  test-fast      - Run tests without coverage (fail fast)"
	@echo "  coverage       - Run tests with detailed coverage report"
	@echo "  chrome-debug   - Launch Chrome with remote debugging for AirDNA scraping"
	@echo "  scrape-airdna  - Run AirDNA scraper standalone"

# Setup target
setup:
	@$(PIPENV) install --dev || exit 1
	$(PIPENV) run playwright install chromium

# Test targets
test:
	$(PYTEST)

test-fast:
	$(PYTEST) -x --no-cov

coverage:
	$(PYTEST) --cov-report=term-missing --cov-report=html:coverage_html
	@echo "Coverage report generated in coverage_html/"

# AirDNA scraper targets
chrome-debug:
	@echo "Launching Chrome with remote debugging on port 9222..."
	@echo "NOTE: Chrome must be fully quit first (Cmd+Q) or the debug port won't open."
	@mkdir -p /tmp/chrome-debug-profile
	/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
		--remote-debugging-port=9222 \
		--user-data-dir=/tmp/chrome-debug-profile &
	@echo "Chrome launched. Verify at http://localhost:9222/json, then log into AirDNA."
	@echo "This uses a separate profile at /tmp/chrome-debug-profile — you may need to log into AirDNA again."

scrape-airdna:
	$(PYTHON) -m scraper.airdna_scraper


.PHONY: default help setup test test-fast coverage run clean chrome-debug scrape-airdna