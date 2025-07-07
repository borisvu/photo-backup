#!/usr/bin/env python3
"""
Test runner for all functional tests
"""

import subprocess
import sys
from pathlib import Path

def run_test_file(test_file):
    """Run a single test file and return success status."""
    print(f"\n{'='*60}")
    print(f"Running {test_file.name}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            [sys.executable, str(test_file)],
            timeout=120  # 2 minutes timeout for tests
        )
        
        if result.returncode == 0:
            print(f"✅ {test_file.name} PASSED")
            return True
        else:
            print(f"❌ {test_file.name} FAILED (exit code: {result.returncode})")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {test_file.name} TIMED OUT")
        return False
    except Exception as e:
        print(f"💥 {test_file.name} ERROR: {e}")
        return False

def discover_tests():
    """Find all test files in the tests directory."""
    tests_dir = Path(__file__).parent
    test_files = []
    
    # Find all test_*.py files except this runner
    for test_file in tests_dir.glob("test_*.py"):
        if test_file.name != "run_all_tests.py":
            test_files.append(test_file)
    
    return sorted(test_files)

def main():
    """Run all discovered tests."""
    print("Photo Backup System - Test Runner")
    print("=" * 60)
    
    test_files = discover_tests()
    
    if not test_files:
        print("No test files found!")
        return 1
    
    print(f"Found {len(test_files)} test file(s):")
    for test_file in test_files:
        print(f"  - {test_file.name}")
    
    # Run all tests
    passed = 0
    failed = 0
    
    for test_file in test_files:
        if run_test_file(test_file):
            passed += 1
        else:
            failed += 1
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Total tests: {len(test_files)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n❌ {failed} TEST(S) FAILED!")
        return 1

if __name__ == "__main__":
    sys.exit(main())