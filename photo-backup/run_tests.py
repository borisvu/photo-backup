#!/usr/bin/env python3
"""
Convenience script to run all tests from project root
"""

import subprocess
import sys
from pathlib import Path

def main():
    """Run the test runner from the tests directory."""
    project_root = Path(__file__).parent
    test_runner = project_root / "tests" / "run_all_tests.py"
    
    if not test_runner.exists():
        print("Test runner not found!")
        return 1
    
    # Execute the test runner
    try:
        result = subprocess.run([sys.executable, str(test_runner)])
        return result.returncode
    except Exception as e:
        print(f"Error running tests: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())