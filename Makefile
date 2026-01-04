# Makefile for setting up the environment and running the AirBNB Review Scraper project

# Variables
PIPENV := pipenv
PYTHON := $(PIPENV) run python
OS := $(shell uname)

# Default target
default: help

# Help target
help:
	@echo "Available targets:"
	@echo "  setup          - Set up the environment (Windows/Unix)"

# Setup target
setup:
	@$(PIPENV) install --dev || exit 1
	pipenv shell


.PHONY: default help setup run clean