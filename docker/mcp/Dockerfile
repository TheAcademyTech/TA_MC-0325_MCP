FROM python:3.12-slim

# Define build arguments
ARG POSTGRES_HOST
ARG POSTGRES_PORT
ARG POSTGRES_DB
ARG POSTGRES_USER
ARG POSTGRES_PASSWORD
ARG DEBUG

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Create virtual environment
RUN uv venv

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/

# Install dependencies using uv
RUN . .venv/bin/activate && uv pip install .

# Set environment variables using build arguments
ENV POSTGRES_HOST=${POSTGRES_HOST} \
    POSTGRES_PORT=${POSTGRES_PORT} \
    POSTGRES_DB=${POSTGRES_DB} \
    POSTGRES_USER=${POSTGRES_USER} \
    POSTGRES_PASSWORD=${POSTGRES_PASSWORD} \
    DEBUG=${DEBUG}

# Run the MCP server
CMD [".venv/bin/python", "src/mcp_server.py"]