#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="dankoiptv",
    version="1.1c-20260906-1450",
    description="Advanced IPTV Player with seamless reconnection for Linux Mint",
    author="Danko Petro",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "requests>=2.25.0",
    ],
    entry_points={
        "console_scripts": [
            "dankoiptv=dankoiptv.main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: POSIX :: Linux",
    ],
)
