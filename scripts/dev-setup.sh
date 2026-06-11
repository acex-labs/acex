#!/usr/bin/env bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}ACE-X Development Environment Setup${NC}"
echo "======================================"

# Check for Poetry
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}Error: Poetry is not installed${NC}"
    echo "Please install Poetry: https://python-poetry.org/docs/#installation"
    exit 1
fi

echo -e "${GREEN}✓ Found Poetry: $(poetry --version)${NC}"

# Get project root (script is in scripts/)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Configure Poetry to create .venv in project directory
echo ""
echo -e "${BLUE}Configuring Poetry${NC}"
poetry config virtualenvs.in-project true
echo -e "${GREEN}✓ Poetry configured to use .venv in each project${NC}"

echo ""
echo -e "${BLUE}Installing packages with Poetry${NC}"
echo ""

install_package() {
    local name=$1
    local dir=$2
    echo -e "${YELLOW}${name}:${NC}"
    cd "$dir"
    # Remove any existing env outside the project dir (e.g. from before virtualenvs.in-project was set)
    if [ ! -d ".venv" ]; then
        poetry env remove --all 2>/dev/null || true
    fi
    poetry install
    echo -e "${GREEN}✓ ${name} installed${NC}"
    echo ""
}

install_package "Devkit"     "$PROJECT_ROOT/devkit"
install_package "Backend"    "$PROJECT_ROOT/backend"
install_package "CLI"        "$PROJECT_ROOT/cli"
install_package "Worker"     "$PROJECT_ROOT/worker"
install_package "MCP Server" "$PROJECT_ROOT/mcp"
echo ""

cd "$PROJECT_ROOT"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Development environment setup complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Activate a package environment:"
echo ""
echo -e "${BLUE}  cd backend  && source .venv/bin/activate${NC}"
echo -e "${BLUE}  cd cli      && source .venv/bin/activate${NC}"
echo -e "${BLUE}  cd worker   && source .venv/bin/activate${NC}"
echo -e "${BLUE}  cd mcp      && source .venv/bin/activate${NC}"
echo -e "${BLUE}  cd devkit   && source .venv/bin/activate${NC}"
echo ""
echo "Switch environment:  deactivate && cd <pkg> && source .venv/bin/activate"
echo "Run without activating:  cd backend && poetry run python script.py"
