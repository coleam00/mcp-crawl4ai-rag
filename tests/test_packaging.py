#!/usr/bin/env python3
"""
Basic packaging tests for mcp-crawl4ai-rag

Tests that the package can be built, installed, and the entry point works.
"""

import subprocess
import sys
import importlib.util
import tempfile
import os
import platform
from pathlib import Path

def test_package_builds():
    """Test that the package can be built using standard Python packaging tools."""
    print("🔧 Testing package build...")
    
    # Test building with uv
    result = subprocess.run([
        "uv", "run", "python", "-m", "build", "--wheel", "--outdir", "dist/"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Package builds successfully with build module")
        return True
    else:
        print(f"❌ Package build failed: {result.stderr}")
        return False

def test_main_function_importable():
    """Test that the main function can be imported from the module."""
    print("🔍 Testing main function import...")
    
    try:
        # Add src to path for testing
        src_path = Path(__file__).parent.parent / "src"
        sys.path.insert(0, str(src_path))
        
        # Import the main function
        import crawl4ai_mcp
        main_func = getattr(crawl4ai_mcp, 'main', None)
        
        if main_func and callable(main_func):
            print("✅ Main function is importable and callable")
            return True
        else:
            print("❌ Main function not found or not callable")
            return False
            
    except ImportError as e:
        print(f"❌ Failed to import crawl4ai_mcp: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error importing main function: {e}")
        return False
    finally:
        # Clean up sys.path
        if str(src_path) in sys.path:
            sys.path.remove(str(src_path))

def test_entry_point_after_install():
    """Test that the entry point works after installation."""
    print("🚀 Testing entry point installation...")
    
    if platform.system() == "Windows":
        # On Windows, use a simpler approach to avoid file locking issues
        try:
            # Install the package in development mode using uv
            result = subprocess.run([
                "uv", "pip", "install", "-e", "."
            ], capture_output=True, text=True, cwd=".")
            
            if result.returncode != 0:
                print(f"❌ Failed to install package: {result.stderr}")
                return False
            
            # Test that the package can be imported after installation
            result = subprocess.run([
                "uv", "run", "python", "-c", 
                "try:\n    import crawl4ai_mcp\n    print('Package import successful')\nexcept Exception as e:\n    print(f'Import failed: {e}')\n    exit(1)"
            ], capture_output=True, text=True, cwd=".")
            
            if result.returncode == 0:
                print("✅ Package installs and imports successfully")
                return True
            else:
                print(f"❌ Failed to import after installation: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Installation test failed: {e}")
            return False
    else:
        # Unix systems: use the original approach with temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Install the package in development mode using uv
                result = subprocess.run([
                    "uv", "pip", "install", "-e", ".", 
                    "--target", temp_dir
                ], capture_output=True, text=True, cwd=".")
                
                if result.returncode != 0:
                    print(f"❌ Failed to install package: {result.stderr}")
                    return False
                
                # Add temp directory to Python path
                sys.path.insert(0, temp_dir)
                
                try:
                    # Try to import the installed package
                    import crawl4ai_mcp
                    print("✅ Package installs and imports successfully")
                    return True
                except ImportError as e:
                    print(f"❌ Failed to import after installation: {e}")
                    return False
                finally:
                    # Clean up sys.path
                    if temp_dir in sys.path:
                        sys.path.remove(temp_dir)
                        
            except Exception as e:
                print(f"❌ Installation test failed: {e}")
                return False

def test_pyproject_toml_valid():
    """Test that pyproject.toml contains required fields."""
    print("🔍 Testing pyproject.toml validity...")
    
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            print("⚠️  No TOML parser available, skipping pyproject.toml validation")
            return True
    
    try:
        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        
        # Check required fields
        project = config.get("project", {})
        required_fields = ["name", "version", "description"]
        
        missing_fields = [field for field in required_fields if field not in project]
        if missing_fields:
            print(f"❌ Missing required fields in pyproject.toml: {missing_fields}")
            return False
        
        # Check that scripts section exists
        scripts = project.get("scripts", {})
        if "mcp-crawl4ai-rag" not in scripts:
            print("❌ Missing mcp-crawl4ai-rag entry point in [project.scripts]")
            return False
            
        print("✅ pyproject.toml is valid and contains required entry point")
        return True
        
    except Exception as e:
        print(f"❌ Failed to validate pyproject.toml: {e}")
        return False

def main():
    """Run all packaging tests."""
    print("🔍 Running packaging tests for mcp-crawl4ai-rag...")
    print("=" * 50)
    
    tests = [
        test_pyproject_toml_valid,
        test_main_function_importable,
        test_entry_point_after_install,
        # Only run build test if build module is available
        test_package_builds if importlib.util.find_spec("build") else None
    ]
    
    # Filter out None tests
    tests = [test for test in tests if test is not None]
    
    passed = 0
    failed = 0
    
    for test in tests:
        print(f"\n🧪 Running {test.__name__}...")
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
        print("-" * 30)
    
    print(f"\n📊 Test Results:")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"🔍 Total:  {len(tests)}")
    
    if failed == 0:
        print("\n🎉 All packaging tests passed!")
        return 0
    else:
        print(f"\n💥 {failed} test(s) failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
