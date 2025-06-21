## Build, Lint, and Test

- **Installation**: `uv pip install -e .` followed by `crawl4ai-setup`
- **Running the server**: `uv run src/crawl4ai_mcp.py`
- **Testing**: No dedicated test suite exists. To test AI hallucination detection, run:
  `python knowledge_graphs/ai_hallucination_detector.py [full path to your script to analyze]`

## Code Style Guidelines

- **Formatting**: Follows standard Python conventions (PEP 8).
- **Imports**: Organized with standard libraries first, followed by third-party libraries, and then local application imports.
- **Typing**: Uses type hints for function signatures (`def my_function(param: str) -> int:`).
- **Naming**:
  - Functions and variables: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
- **Error Handling**: Uses `try...except` blocks for operations that can fail, like API calls or file I/O.
- **Docstrings**: Uses triple-quote docstrings to explain the purpose of functions and modules.
- **Environment Variables**: Configuration is managed through a `.env` file.
- **Concurrency**: Uses `asyncio` for asynchronous operations and `concurrent.futures.ThreadPoolExecutor` for parallel processing.
