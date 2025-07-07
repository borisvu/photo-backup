"""Setup configuration for photo backup system."""

from setuptools import setup, find_packages
from pathlib import Path

# Read version from __version__.py
version_file = Path(__file__).parent / "photo_backup" / "__version__.py"
version_dict = {}
with open(version_file) as f:
    exec(f.read(), version_dict)

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
with open(requirements_file) as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="photo-backup",
    version=version_dict["__version__"],
    description="Automated photo backup system to S3-compatible storage",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "photo-backup=photo_backup.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)