# Tuxbox-OS Builder - Main Makefile
# Production-ready build orchestrator for Tuxbox-Neutrino
#
# Usage:
#   make image MACHINE=hd51              # Build image
#   make feeds MACHINE=hd51              # Build package feeds
#   make clean                           # Clean build (keeps sstate)
#   make list-machines                   # Show all supported machines
#   make help                            # Show this help

SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

# Colors for output
COLOR_RESET := \033[0m
COLOR_BOLD := \033[1m
COLOR_RED := \033[31m
COLOR_GREEN := \033[32m
COLOR_YELLOW := \033[33m
COLOR_BLUE := \033[34m

# Configuration
MACHINE ?= hd51
MACHINEBUILD ?= $(MACHINE)
DISTRO ?= tuxbox
DISTRO_TYPE ?= release
TOPDIR := $(CURDIR)

# Build directories
BUILDDIR := $(TOPDIR)/build
DL_DIR := $(TOPDIR)/downloads
SSTATE_DIR := $(TOPDIR)/sstate-cache

# State tracking
STATE_FILE := $(TOPDIR)/.tuxbox/state.json

# Python CLI
CLI := $(TOPDIR)/cli.py

# Check if Python CLI is available
ifeq ($(wildcard $(CLI)),)
    USE_CLI := 0
else
    USE_CLI := 1
endif

.PHONY: help
help:
	@echo -e "$(COLOR_BOLD)Tuxbox-OS Builder$(COLOR_RESET)"
	@echo ""
	@echo -e "$(COLOR_BOLD)Basic Commands:$(COLOR_RESET)"
	@echo -e "  $(COLOR_GREEN)make image MACHINE=hd51$(COLOR_RESET)              Build complete image"
	@echo -e "  $(COLOR_GREEN)make feeds MACHINE=hd51$(COLOR_RESET)              Build package feeds"
	@echo -e "  $(COLOR_GREEN)make sdk MACHINE=hd51$(COLOR_RESET)                Build SDK for development"
	@echo ""
	@echo -e "$(COLOR_BOLD)Maintenance:$(COLOR_RESET)"
	@echo -e "  $(COLOR_GREEN)make clean$(COLOR_RESET)                           Clean build artifacts (keeps sstate)"
	@echo -e "  $(COLOR_GREEN)make distclean$(COLOR_RESET)                       Clean everything"
	@echo -e "  $(COLOR_GREEN)make update$(COLOR_RESET)                          Update submodules"
	@echo ""
	@echo -e "$(COLOR_BOLD)Information:$(COLOR_RESET)"
	@echo -e "  $(COLOR_GREEN)make list-machines$(COLOR_RESET)                   List all supported machines"
	@echo -e "  $(COLOR_GREEN)make machine-info MACHINE=hd51$(COLOR_RESET)       Show machine details"
	@echo -e "  $(COLOR_GREEN)make check$(COLOR_RESET)                           Check system prerequisites"
	@echo ""
	@echo -e "$(COLOR_BOLD)Advanced (Python CLI):$(COLOR_RESET)"
	@echo -e "  $(COLOR_GREEN)./cli.py init$(COLOR_RESET)                        Initialize build environment"
	@echo -e "  $(COLOR_GREEN)./cli.py build -m hd51$(COLOR_RESET)               Build with Python CLI"
	@echo -e "  $(COLOR_GREEN)./cli.py build -m hd51 --offline$(COLOR_RESET)     Build offline"
	@echo -e "  $(COLOR_GREEN)./cli.py build -m hd51 --devshell$(COLOR_RESET)    Drop to devshell"
	@echo -e "  $(COLOR_GREEN)./cli.py --help$(COLOR_RESET)                      Show all CLI options"
	@echo ""
	@echo -e "$(COLOR_BOLD)Variables:$(COLOR_RESET)"
	@echo -e "  MACHINE      Target hardware (default: hd51)"
	@echo -e "  MACHINEBUILD OEM variant (default: MACHINE)"
	@echo -e "  DISTRO       Distribution (default: tuxbox)"
	@echo -e "  DISTRO_TYPE  Build type: release|development (default: release)"
	@echo ""
	@echo -e "$(COLOR_BOLD)Examples:$(COLOR_RESET)"
	@echo -e "  $(COLOR_YELLOW)make image MACHINE=hd60$(COLOR_RESET)"
	@echo -e "  $(COLOR_YELLOW)make image MACHINE=zgemmah7 DISTRO_TYPE=development$(COLOR_RESET)"
	@echo ""

.PHONY: check
check:
	@echo -e "$(COLOR_BOLD)Checking system prerequisites...$(COLOR_RESET)"
ifeq ($(USE_CLI),1)
	@$(CLI) check
else
	@$(TOPDIR)/scripts/check-prerequisites.sh
endif

.PHONY: init
init: check
	@echo -e "$(COLOR_BOLD)Initializing Tuxbox-OS build environment...$(COLOR_RESET)"
ifeq ($(USE_CLI),1)
	@$(CLI) init
else
	@$(TOPDIR)/scripts/init.sh
endif

.PHONY: image
image: init
	@echo -e "$(COLOR_BOLD)Building image for $(COLOR_YELLOW)$(MACHINE)$(COLOR_RESET)..."
ifeq ($(USE_CLI),1)
	@$(CLI) build --machine $(MACHINE) --machinebuild $(MACHINEBUILD) --distro $(DISTRO) --distro-type $(DISTRO_TYPE)
else
	@echo -e "$(COLOR_RED)Error: cli.py not found. Please run 'make init' first.$(COLOR_RESET)"
	@exit 1
endif

.PHONY: feeds
feeds: init
	@echo -e "$(COLOR_BOLD)Building package feeds for $(COLOR_YELLOW)$(MACHINE)$(COLOR_RESET)..."
ifeq ($(USE_CLI),1)
	@$(CLI) build --machine $(MACHINE) --machinebuild $(MACHINEBUILD) --target feeds
else
	@echo -e "$(COLOR_RED)Error: cli.py not found.$(COLOR_RESET)"
	@exit 1
endif

.PHONY: sdk
sdk: init
	@echo -e "$(COLOR_BOLD)Building SDK for $(COLOR_YELLOW)$(MACHINE)$(COLOR_RESET)..."
ifeq ($(USE_CLI),1)
	@$(CLI) build --machine $(MACHINE) --machinebuild $(MACHINEBUILD) --target sdk
else
	@echo -e "$(COLOR_RED)Error: cli.py not found.$(COLOR_RESET)"
	@exit 1
endif

.PHONY: devshell
devshell: init
	@echo -e "$(COLOR_BOLD)Starting development shell for $(COLOR_YELLOW)$(MACHINE)$(COLOR_RESET)..."
ifeq ($(USE_CLI),1)
	@$(CLI) build --machine $(MACHINE) --machinebuild $(MACHINEBUILD) --devshell
else
	@echo -e "$(COLOR_RED)Error: cli.py not found.$(COLOR_RESET)"
	@exit 1
endif

.PHONY: clean
clean:
	@echo -e "$(COLOR_BOLD)Cleaning build artifacts (keeping sstate-cache)...$(COLOR_RESET)"
	@rm -rf $(BUILDDIR)/tmp
	@echo -e "$(COLOR_GREEN)Build artifacts cleaned.$(COLOR_RESET)"

.PHONY: distclean
distclean:
	@echo -e "$(COLOR_BOLD)$(COLOR_RED)Warning: This will delete all builds and caches!$(COLOR_RESET)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -rf $(BUILDDIR) $(SSTATE_DIR) $(DL_DIR); \
		rm -f $(STATE_FILE); \
		echo -e "$(COLOR_GREEN)Everything cleaned.$(COLOR_RESET)"; \
	else \
		echo -e "$(COLOR_YELLOW)Cancelled.$(COLOR_RESET)"; \
	fi

.PHONY: update
update:
	@echo -e "$(COLOR_BOLD)Updating submodules...$(COLOR_RESET)"
	@git submodule update --remote --recursive
	@echo -e "$(COLOR_GREEN)Submodules updated.$(COLOR_RESET)"

.PHONY: list-machines
list-machines:
	@echo -e "$(COLOR_BOLD)Supported machines:$(COLOR_RESET)"
	@echo ""
	@echo -e "$(COLOR_BOLD)Priority platforms (tested):$(COLOR_RESET)"
	@echo -e "  $(COLOR_GREEN)GFutures:$(COLOR_RESET)   hd51, hd60, hd61"
	@echo -e "  $(COLOR_GREEN)AirDigital:$(COLOR_RESET) zgemmah7, h7s, h7c"
	@echo -e "  $(COLOR_GREEN)Coolstream:$(COLOR_RESET) tank (uClibc)"
	@echo ""
	@echo -e "$(COLOR_YELLOW)For complete list (300+ devices), see OE-Alliance documentation.$(COLOR_RESET)"
	@echo ""

.PHONY: machine-info
machine-info:
	@echo -e "$(COLOR_BOLD)Machine info for $(COLOR_YELLOW)$(MACHINE)$(COLOR_RESET):"
	@$(TOPDIR)/scripts/machine-info.sh $(MACHINE)

.PHONY: test
test:
	@echo -e "$(COLOR_BOLD)Running tests...$(COLOR_RESET)"
	@pytest tests/ -v

# Special target for CI
.PHONY: ci-build
ci-build: init
	@$(CLI) build --machine $(MACHINE) --machinebuild $(MACHINEBUILD) --ci-mode

.PHONY: version
version:
	@echo "Tuxbox-OS Builder v1.0.0"
	@echo "Yocto: Kirkstone (4.0 LTS)"
	@echo "Python: $$(python3 --version)"
	@echo "Git: $$(git --version)"
