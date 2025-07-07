#!/usr/bin/env python3
"""Simple test to verify Docker connectivity."""

import sys
import subprocess

def test_docker_cli():
    """Test Docker CLI access."""
    try:
        result = subprocess.run(['docker', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ Docker CLI available: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ Docker CLI failed: {result.stderr}")
            return False
    except FileNotFoundError:
        print("❌ Docker command not found")
        return False
    except subprocess.TimeoutExpired:
        print("❌ Docker command timed out")
        return False

def test_docker_daemon():
    """Test Docker daemon connectivity."""
    try:
        result = subprocess.run(['docker', 'ps'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ Docker daemon accessible")
            return True
        else:
            print(f"❌ Docker daemon not accessible: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Docker daemon connection timed out")
        return False

def test_docker_python():
    """Test Python Docker client."""
    try:
        import docker
        print("✅ Docker Python package imported")
        
        client = docker.from_env()
        print("✅ Docker client created")
        
        version = client.version()
        print(f"✅ Docker API version: {version.get('ApiVersion', 'unknown')}")
        return True
        
    except ImportError:
        print("❌ Docker Python package not installed")
        return False
    except Exception as e:
        print(f"❌ Docker Python client failed: {e}")
        return False

def main():
    """Run all Docker tests."""
    print("Testing Docker connectivity...\n")
    
    cli_ok = test_docker_cli()
    daemon_ok = test_docker_daemon()
    python_ok = test_docker_python()
    
    print(f"\nResults:")
    print(f"Docker CLI: {'✅' if cli_ok else '❌'}")
    print(f"Docker Daemon: {'✅' if daemon_ok else '❌'}")
    print(f"Python Client: {'✅' if python_ok else '❌'}")
    
    if all([cli_ok, daemon_ok, python_ok]):
        print("\n🎉 All Docker tests passed! Test infrastructure should work.")
        return 0
    else:
        print("\n⚠️  Some Docker tests failed. Please fix Docker setup before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())