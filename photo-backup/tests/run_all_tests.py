#!/usr/bin/env python3
"""
Test runner for all functional tests using pytest
"""

import subprocess
import sys
from pathlib import Path

def main():
    """Run all tests using pytest."""
    print("Photo Backup System - Pytest Test Runner")
    print("=" * 60)
    
    # Get the project root directory (parent of tests/)
    project_root = Path(__file__).parent.parent
    
    # Run pytest from the project root
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest",
            "-v",  # verbose output
            "--tb=short",  # short traceback format
            "tests/"  # test directory
        ], cwd=project_root)
        
        return result.returncode
        
    except Exception as e:
        print(f"Error running pytest: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())