#!/usr/bin/env bash

# Elastro CLI Installer
# This script intelligently checks for Python and pipx, installs pipx if missing (macOS/Ubuntu),
# verifies Python compatibility, and installs elastro-client securely.

set -e

# ANSI Color Codes
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}=======================================${NC}"
echo -e "${CYAN}       Elastro Install Wizard          ${NC}"
echo -e "${CYAN}=======================================${NC}\n"

# 1. Dependency Checks & Resolution
echo -e "${YELLOW}[1/4] Checking System Requirements...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is not installed. Please install Python 3.9+ first.${NC}"
    exit 1
fi

# Determine Python Version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]; }; then
    echo -e "${RED}Error: Python version must be >= 3.9. Found: $PYTHON_VERSION${NC}"
    exit 1
fi

if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 14 ]; then
    echo -e "${RED}Error: Python $PYTHON_VERSION is too new and not yet supported due to PyO3 native extensions.${NC}"
    echo -e "${RED}Please install Python 3.13 or lower. (e.g., brew install python@3.13)${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python $PYTHON_VERSION detected and compatible.${NC}"

# Check for pipx
if ! command -v pipx &> /dev/null; then
    echo -e "${YELLOW}! pipx is not installed. Attempting automatic installation...${NC}"
    
    if [[ "$OSTYPE" == "darwin"* ]] && command -v brew &> /dev/null; then
        echo -e "Running: brew install pipx"
        brew install pipx
    elif [[ "$OSTYPE" == "linux-gnu"* ]] && command -v apt-get &> /dev/null; then
        echo -e "Running: sudo apt-get update && sudo apt-get install -y pipx"
        sudo apt-get update
        sudo apt-get install -y pipx
    else
        echo -e "${RED}Error: Could not install pipx automatically. Please install pipx manually: https://pipx.pypa.io/stable/installation/${NC}"
        exit 1
    fi
fi

# Ensure pipx path
echo -e "${YELLOW}[2/4] Ensuring pipx PATH configuration...${NC}"
pipx ensurepath
export PATH="$PATH:$HOME/.local/bin" # Inject locally for this session just in case

# 2. Install Elastro
echo -e "\n${YELLOW}[3/4] Installing elastro-client...${NC}"
# Use the explicit safe python binary to prevent pipx from defaulting to a bad system wrapper
pipx install elastro-client --python $(which python3) --force

# 3. Validation
echo -e "\n${YELLOW}[4/4] Validating Installation...${NC}"
if command -v elastro &> /dev/null; then
    echo -e "${GREEN}=======================================${NC}"
    echo -e "${GREEN}✓ Success! Elastro is now installed.${NC}"
    echo -e "${GREEN}=======================================${NC}"
    echo -e "You can now run: ${CYAN}elastro --help${NC}"
    echo -e "\n${YELLOW}Note: If the 'elastro' command is not found, please restart your terminal or run: source ~/.bashrc (or ~/.zshrc)${NC}"
else
    echo -e "${RED}Installation completed but 'elastro' command not found in PATH. Please restart your terminal.${NC}"
fi
