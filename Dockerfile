FROM python:3.12-slim

ARG PORT=8051

WORKDIR /app

# Install uv
RUN pip install uv

# Copy the MCP server files
COPY . .

# Install packages directly to the system (no virtual environment)
# Combining commands to reduce Docker layers
RUN uv pip install --system -e . && \
    crawl4ai-setup

EXPOSE ${PORT}

# Command to run the MCP server
CMD ["crawl4ai-mcp"]
