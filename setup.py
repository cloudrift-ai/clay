"""Setup script for Clay."""

from setuptools import setup, find_packages

setup(
    name="clay",
    version="0.1.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "clay=clay.cli:main",
        ],
    },
)