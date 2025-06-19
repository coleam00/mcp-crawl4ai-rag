#!/usr/bin/env python3
"""
Simple linting script for the project.

Runs formatting and linting tools in the correct order.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and print the result."""
    print(f"\n🔍 {description}")
    print(f"Running: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        return False


def main():
    """Run all linting tools."""
    print("🚀 Running linting and formatting tools...")
    
    # Change to script directory
    script_dir = Path(__file__).parent
    src_dir = script_dir / "src"
    
    if not src_dir.exists():
        print(f"❌ Source directory not found: {src_dir}")
        sys.exit(1)
    
    # Commands to run
    commands = [
        # Format with black
        (
            [sys.executable, "-m", "black", str(src_dir)],
            "Code formatting with Black"
        ),
        
        # Sort imports
        (
            [sys.executable, "-m", "isort", str(src_dir)],
            "Import sorting with isort"
        ),
        
        # Run pylint
        (
            [sys.executable, "-m", "pylint", str(src_dir)],
            "Code linting with Pylint"
        ),
    ]
    
    success_count = 0
    total_count = len(commands)
    
    for cmd, description in commands:
        if run_command(cmd, description):
            success_count += 1
    
    print(f"\n{'='*60}")
    print(f"📊 Linting Summary: {success_count}/{total_count} tools completed successfully")
    
    if success_count == total_count:
        print("🎉 All linting checks passed!")
        sys.exit(0)
    else:
        print("⚠️  Some linting tools reported issues")
        sys.exit(1)


if __name__ == "__main__":
    main() 