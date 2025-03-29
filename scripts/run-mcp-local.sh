#!/bin/bash

# Script to run the MCP server locally using the uv virtual environment with Python 3.12

# Source the virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Virtual environment not found. Please run setup-dev-env.sh first."
    exit 1
fi

# Verify we're using Python 3.12
PYTHON_VERSION=$(python --version)
if [[ $PYTHON_VERSION != *"Python 3.12"* ]]; then
    echo "Warning: Not using Python 3.12. Current version: $PYTHON_VERSION"
    echo "Please ensure your virtual environment is using Python 3.12"
    exit 1
fi

# Load environment variables from .env file
if [ -f ".env" ]; then
    echo "Loading environment variables from .env file..."
    export $(grep -v '^#' .env | xargs)
    
    # Override POSTGRES_HOST for local development (connecting to Docker container)
    export POSTGRES_HOST="localhost"
else
    echo "Warning: .env file not found. Using default environment variables."
    # Set default environment variables for local development
    export POSTGRES_HOST="localhost"
    export POSTGRES_PORT="5432"
    export POSTGRES_DB="learning_analytics"
    export POSTGRES_USER="admin"
    export POSTGRES_PASSWORD="admin123"
    export DEBUG="true"
fi

# Run the MCP server
echo "Starting MCP server locally with Python 3.12..."
echo "Connecting to PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT} as ${POSTGRES_USER}"
python src/mcp_server.py