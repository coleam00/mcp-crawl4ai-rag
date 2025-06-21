#!/usr/bin/env python3
"""
Test script for parse_github_repository function
Tests the fixed version that handles SSE communication errors
"""

import requests
import json
import time


def test_parse_github_repository():
    """Test the parse_github_repository function via HTTP."""
    
    print("🧪 Testing parse_github_repository function")
    print("=" * 50)
    
    # Test with a small repository to avoid long processing
    test_repos = [
        "https://github.com/python/cpython.git",  # Large repo (stress test)
        "https://github.com/pallets/flask.git",   # Medium repo
        "https://github.com/psf/requests.git"    # Smaller repo
    ]
    
    print("Available test repositories:")
    for i, repo in enumerate(test_repos, 1):
        print(f"  {i}. {repo}")
    
    choice = input("\nChoose a repository (1-3) or enter custom URL: ").strip()
    
    if choice.isdigit() and 1 <= int(choice) <= len(test_repos):
        repo_url = test_repos[int(choice) - 1]
    else:
        repo_url = choice if choice.startswith('http') else test_repos[1]  # Default to Flask
    
    print(f"\n🔄 Testing with: {repo_url}")
    print("⚠️  This may take several minutes for large repositories...")
    print("⏱️  Timeout is set to 30 minutes")
    
    # Test via MCP server health check first
    try:
        health_response = requests.get("http://localhost:8051/health", timeout=10)
        if health_response.status_code == 200:
            print("✅ MCP server is responding")
        else:
            print("❌ MCP server not responding properly")
            return
    except Exception as e:
        print(f"❌ Cannot connect to MCP server: {e}")
        print("   Make sure Docker containers are running: docker-compose up -d")
        return
    
    # Prepare the MCP tool call
    # Note: This is a direct HTTP approach - adjust based on your MCP setup
    payload = {
        "tool": "parse_github_repository",
        "arguments": {
            "repo_url": repo_url
        }
    }
    
    print(f"\n📡 Sending request to MCP server...")
    start_time = time.time()
    
    try:
        # Try multiple endpoint patterns
        endpoints = [
            "http://localhost:8051/tools/parse_github_repository",
            "http://localhost:8051/parse_github_repository",
            "http://localhost:8051/mcp/tools/parse_github_repository"
        ]
        
        response = None
        for endpoint in endpoints:
            try:
                response = requests.post(
                    endpoint,
                    json=payload,
                    timeout=1800,  # 30 minutes
                    headers={"Content-Type": "application/json"}
                )
                if response.status_code == 200:
                    break
            except requests.exceptions.RequestException:
                continue
        
        if not response or response.status_code != 200:
            print("❌ Could not call parse_github_repository via HTTP endpoints")
            print("   The function may only be available via MCP protocol")
            print("   Try using a proper MCP client instead")
            return
        
        elapsed = time.time() - start_time
        print(f"✅ Request completed in {elapsed:.2f} seconds")
        
        # Parse response
        try:
            result = response.json()
            print("\n📊 Results:")
            print(json.dumps(result, indent=2))
            
            if result.get("success"):
                stats = result.get("stats", {})
                print(f"\n🎯 Summary:")
                print(f"  Repository: {result.get('repo_name', 'unknown')}")
                print(f"  Files processed: {stats.get('files_processed', 0)}")
                print(f"  Classes created: {stats.get('classes_created', 0)}")
                print(f"  Methods created: {stats.get('methods_created', 0)}")
                print(f"  Functions created: {stats.get('functions_created', 0)}")
                print(f"  Total nodes: {stats.get('total_nodes', 0)}")
                print(f"  Processing time: {elapsed:.2f} seconds")
                
                if result.get("note"):
                    print(f"  Note: {result.get('note')}")
                
                print("\n✅ Repository parsing completed successfully!")
            else:
                print(f"\n❌ Parsing failed: {result.get('error', 'Unknown error')}")
                
        except json.JSONDecodeError:
            print(f"❌ Invalid JSON response: {response.text[:200]}...")
            
    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        print(f"\n⏰ Request timed out after {elapsed:.2f} seconds")
        print("   This is normal for very large repositories")
        print("   Check the Docker logs to see if processing is still ongoing")
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ Request failed after {elapsed:.2f} seconds: {e}")
    
    print("\n" + "=" * 50)
    print("🏁 Test completed")


def show_usage():
    """Show usage information."""
    print("""
🧪 Parse GitHub Repository Test

This script tests the fixed parse_github_repository function.

Requirements:
1. MCP server running: docker-compose up -d
2. Neo4j enabled: USE_KNOWLEDGE_GRAPH=true in .env
3. Git installed in container (fixed in latest Dockerfile)

The test will:
- Check MCP server connectivity
- Send a parse request for a GitHub repository
- Show processing statistics
- Handle SSE communication errors gracefully

Note: Large repositories may take 10-30 minutes to process.
""")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help", "help"]:
        show_usage()
    else:
        test_parse_github_repository()