"""
Photo fixtures for photo backup system tests.

This module provides utilities for creating test photo data and managing test infrastructure.
"""

import os
import random
import string
import shutil
from pathlib import Path
from typing import List, Tuple


def generate_test_photos(base_dir: str = "/tmp/photo-backup-test-photos", 
                        num_files: int = 20,
                        min_size_mb: int = 1,
                        max_size_mb: int = 10) -> Path:
    """Generate realistic test photo files with various formats and sizes.
    
    Args:
        base_dir: Base directory for test photos
        num_files: Number of files to generate
        min_size_mb: Minimum file size in MB
        max_size_mb: Maximum file size in MB
        
    Returns:
        Path to the created test photo directory
    """
    base_path = Path(base_dir)
    
    # Clean up existing directory
    if base_path.exists():
        shutil.rmtree(base_path)
    
    # Create base directory
    base_path.mkdir(parents=True, exist_ok=True)
    
    # Photo file extensions to use
    extensions = ['.jpeg', '.jpg', '.dng', '.cr2']
    
    # Generate files across multiple years and months
    years = [2023, 2024, 2025]
    months = list(range(1, 13))
    
    files_created = []
    
    for i in range(num_files):
        # Random year and month
        year = random.choice(years)
        month = random.choice(months)
        
        # Create year/month directory
        photo_dir = base_path / str(year) / f"{month:02d}"
        photo_dir.mkdir(parents=True, exist_ok=True)
        
        # Random file extension
        ext = random.choice(extensions)
        
        # Generate filename
        filename = f"IMG_{i+1:04d}{ext}"
        file_path = photo_dir / filename
        
        # Generate random content with specified size
        file_size_mb = random.uniform(min_size_mb, max_size_mb)
        file_size_bytes = int(file_size_mb * 1024 * 1024)
        
        # Generate random text content
        content = _generate_random_content(file_size_bytes)
        
        # Write file
        file_path.write_text(content)
        files_created.append(file_path)
    
    return base_path


def _generate_random_content(size_bytes: int) -> str:
    """Generate random text content of specified size.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Random text content
    """
    # Use a mix of characters to make it more realistic
    chars = string.ascii_letters + string.digits + string.punctuation + " \n\t"
    
    # Generate content in chunks to avoid memory issues
    chunk_size = 1024
    content = ""
    
    while len(content.encode('utf-8')) < size_bytes:
        chunk = ''.join(random.choice(chars) for _ in range(chunk_size))
        content += chunk
    
    # Trim to exact size
    while len(content.encode('utf-8')) > size_bytes:
        content = content[:-1]
    
    return content


def cleanup_test_photos(base_dir: str = "/tmp/photo-backup-test-photos") -> bool:
    """Clean up test photo directory.
    
    Args:
        base_dir: Base directory to clean up
        
    Returns:
        True if cleanup successful, False otherwise
    """
    try:
        base_path = Path(base_dir)
        if base_path.exists():
            shutil.rmtree(base_path)
        return True
    except Exception:
        return False


def get_test_photo_stats(base_dir: str = "/tmp/photo-backup-test-photos") -> dict:
    """Get statistics about test photos.
    
    Args:
        base_dir: Base directory to analyze
        
    Returns:
        Dictionary with statistics
    """
    base_path = Path(base_dir)
    if not base_path.exists():
        return {"error": "Directory does not exist"}
    
    stats = {
        "total_files": 0,
        "total_size_bytes": 0,
        "file_types": {},
        "year_month_structure": {},
        "largest_file": None,
        "smallest_file": None
    }
    
    largest_size = 0
    smallest_size = float('inf')
    
    for file_path in base_path.rglob("*"):
        if file_path.is_file():
            stats["total_files"] += 1
            file_size = file_path.stat().st_size
            stats["total_size_bytes"] += file_size
            
            # Track file types
            ext = file_path.suffix.lower()
            stats["file_types"][ext] = stats["file_types"].get(ext, 0) + 1
            
            # Track year/month structure
            try:
                year_month = f"{file_path.parent.parent.name}/{file_path.parent.name}"
                stats["year_month_structure"][year_month] = stats["year_month_structure"].get(year_month, 0) + 1
            except (IndexError, AttributeError):
                pass
            
            # Track largest and smallest files
            if file_size > largest_size:
                largest_size = file_size
                stats["largest_file"] = str(file_path)
            if file_size < smallest_size:
                smallest_size = file_size
                stats["smallest_file"] = str(file_path)
    
    return stats 