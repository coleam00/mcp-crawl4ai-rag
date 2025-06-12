#!/usr/bin/env bash
# Quick local test script for packaging

set -e

echo "🔍 Running local packaging tests..."
echo "=================================="

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ pyproject.toml not found. Run this script from the project root."
    exit 1
fi

echo "📋 Step 1: Validating pyproject.toml..."
python -c "
import sys
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        print('⚠️  No TOML parser available. Install with: pip install tomli')
        sys.exit(1)

with open('pyproject.toml', 'rb') as f:
    config = tomllib.load(f)

project = config.get('project', {})
print(f'📦 Package: {project.get(\"name\", \"Unknown\")} v{project.get(\"version\", \"Unknown\")}')

scripts = project.get('scripts', {})
if 'mcp-crawl4ai-rag' in scripts:
    print(f'🚀 Entry point: {scripts[\"mcp-crawl4ai-rag\"]}')
else:
    print('❌ Entry point not found!')
    sys.exit(1)
"

echo "✅ pyproject.toml looks good!"
echo ""

echo "🧪 Step 2: Running packaging tests..."
if [ -f "tests/test_packaging.py" ]; then
    python tests/test_packaging.py
else
    echo "❌ Test file not found!"
    exit 1
fi

echo ""
echo "🔧 Step 3: Testing build process..."

# Clean previous builds
rm -rf dist/ build/ *.egg-info/

# Try to build the package
if command -v uv &> /dev/null; then
    echo "Using uv to install build dependencies..."
    uv pip install build
    echo "Building with uv run..."
    uv run python -m build --wheel --outdir dist/
else
    echo "uv not found, using pip..."
    pip install build
    python -m build --wheel --outdir dist/
fi

if [ -f dist/*.whl ]; then
    echo "✅ Package built successfully!"
    ls -la dist/
else
    echo "❌ Package build failed!"
    exit 1
fi

echo ""
echo "🎉 All local tests passed!"
echo "You can now push your changes to trigger CI."
