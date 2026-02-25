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
	@echo "  setup          - Set up the environment (Windows/Unix)"
	@echo "  test           - Run all tests with coverage"
	@echo "  test-fast      - Run tests without coverage (fail fast)"
	@echo "  coverage       - Run tests with detailed coverage report"

# Setup target
setup:
	@$(PIPENV) install --dev || exit 1
	pipenv shell

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
	open -a "Google Chrome" --args --remote-debugging-port=9222
	@echo "Chrome launched. Log into AirDNA, then run 'make scrape-airdna'"

scrape-airdna:
	$(PYTHON) -m scraper.airdna_scraper


.PHONY: default help setup test test-fast coverage run clean chrome-debug scrape-airdna