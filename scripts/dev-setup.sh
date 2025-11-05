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

# Install backend
echo -e "${YELLOW}Backend:${NC}"
cd "$PROJECT_ROOT/backend"
poetry install
echo -e "${GREEN}✓ Backend installed${NC}"
echo ""

# Install CLI
echo -e "${YELLOW}CLI:${NC}"
cd "$PROJECT_ROOT/cli"
poetry install
echo -e "${GREEN}✓ CLI installed${NC}"
echo ""

# Install Worker
echo -e "${YELLOW}Worker:${NC}"
cd "$PROJECT_ROOT/worker"
poetry install
echo -e "${GREEN}✓ Worker installed${NC}"
echo ""

# Install MCP Server
echo -e "${YELLOW}MCP Server:${NC}"
cd "$PROJECT_ROOT/mcp"
poetry install
echo -e "${GREEN}✓ MCP Server installed${NC}"
echo ""

cd "$PROJECT_ROOT"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Development environment setup complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "To work on a specific package:"
echo ""
echo -e "${BLUE}Backend:${NC}"
echo "  cd backend && poetry shell"
echo ""
echo -e "${BLUE}CLI:${NC}"
echo "  cd cli && poetry shell"
echo ""
echo -e "${BLUE}Worker:${NC}"
echo "  cd worker && poetry shell"
echo ""
echo -e "${BLUE}MCP Server:${NC}"
echo "  cd mcp && poetry shell"
echo ""
echo "Or run commands directly with:"
echo "  cd backend && poetry run python script.py"
