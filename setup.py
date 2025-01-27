from setuptools import setup, find_packages
from pybalt.core import constants


def readme():
    with open("README.md", "r") as f:
        return f.read()


setup(
    name="pybalt",
    version=constants.VERSION,
    author="nichind",
    author_email="nichinddev@gmail.com",
    description="tool/python-module for downloading videos from YouTube, Twitter (X), Instagram, Reddit, Soundcloud and more! Powered by the @imputnet cobalt instances.",
    long_description=readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/nichind/pybalt",
    packages=find_packages(),
    package_data={
        "pybalt": ["locales/*.txt"],
    },
    install_requires=[x.strip() for x in open("requirements.txt").readlines()],
    keywords=[
        "downloader",
        "cobalt",
        "cobalt-cli",
        "youtube",
        "twitter",
        "x",
        "instagram",
        "reddit",
        "twitch",
        "bilibili",
        "download",
        "youtube-downloader",
        "twitter-downloader",
        "x-downloader",
        "instagram-downloader",
        "reddit-downloader",
        "twitch-downloader",
        "bilibili-downloader",
    ],
    classifiers=[
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.11",
    entry_points={
        "console_scripts": [
            "pybalt=pybalt.__main__:main",
            "cobalt=pybalt.__main__:main",
        ],
    },
)
