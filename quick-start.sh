#!/bin/bash
# Quick start script for Crawl4AI RAG MCP Server with Docker Compose

set -e

echo "🚀 Crawl4AI RAG MCP Server Quick Start"
echo "======================================"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "📋 Creating .env file from template..."
    cp .env.example .env
    echo "✅ Created .env file"
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env and set your actual values for:"
    echo "   - OPENAI_API_KEY"
    echo "   - SUPABASE_URL"
    echo "   - SUPABASE_SERVICE_KEY"
    echo "   - NEO4J_PASSWORD"
    echo ""
    echo "After editing .env, run this script again or use: docker compose up --build"
    exit 1
else
    echo "✅ Found .env file"
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Please start Docker Desktop and try again."
    exit 1
else
    echo "✅ Docker is running"
fi

# Check if docker compose is available
if ! docker compose version &> /dev/null; then
    echo "❌ docker compose is not available. Please install Docker Compose."
    exit 1
else
    echo "✅ Docker Compose is available"
fi

# Create Neo4j directories if they don't exist
if [ ! -d "neo4j/data" ]; then
    echo "📁 Creating Neo4j directories..."
    mkdir -p neo4j/data neo4j/logs
    echo "✅ Created Neo4j directories"
fi

# Check environment variables
echo "🔍 Checking environment variables..."
if ! grep -q "OPENAI_API_KEY=sk-" .env; then
    echo "⚠️  OPENAI_API_KEY appears to be empty in .env file"
fi

if ! grep -q "SUPABASE_URL=https://" .env; then
    echo "⚠️  SUPABASE_URL appears to be empty in .env file"
fi

if ! grep -q "NEO4J_PASSWORD=.." .env; then
    echo "⚠️  NEO4J_PASSWORD appears to be empty in .env file"
fi

echo ""
echo "🐳 Starting Docker Compose services..."
echo "This may take a few minutes on first run..."
echo ""

# Start services
docker compose up --build -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service health
echo "🏥 Checking service health..."
docker compose ps

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Access your services:"
echo "🌐 MCP Server: http://localhost:8051"
echo "🔍 Neo4j Browser: http://localhost:7474"
echo "📊 Neo4j Bolt: bolt://localhost:7687"
echo ""
echo "Useful commands:"
echo "📊 View logs: docker compose logs -f"
echo "🛑 Stop services: docker compose down"
echo "🗑️  Clean up: docker compose down -v"
echo ""
echo "For troubleshooting, see the Docker Compose Troubleshooting section in README.md"