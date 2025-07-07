#!/usr/bin/env python3
"""
Convenience script to run all tests using pytest from project root
"""

import subprocess
import sys
from pathlib import Path

def main():
    """Run pytest from the project root."""
    project_root = Path(__file__).parent
    
    # Execute pytest
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