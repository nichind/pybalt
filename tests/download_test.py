import pytest
import asyncio
import os

from pybalt import download

YOUTUBE_TEST_LINK = "https://www.youtube.com/watch?v=EFsSYiNl2AQ"
YOUTUBE_TEST_TITLE = "【Ado】ヒバナ 歌いました"

@pytest.mark.asyncio
async def test_download_youtube():
    # Download the video
    downloaded = (await download(YOUTUBE_TEST_LINK, filenameStyle="basic", videoQuality="1080"))[0]
    path = downloaded[1]
    
    # Check if the file exists
    assert os.path.exists(path), f"File {path} does not exist"

    # Check if filename contains the video title
    assert YOUTUBE_TEST_TITLE in path.name, f"Filename {path} does not contain the video title {downloaded.name}"
    
    # Check if the video is in correct resolution
    assert "1080p" in path.name, f"Video resolution {downloaded[0].resolution} is not 1080p" 
    
    # Check if the file is not empty
    assert os.path.getsize(path) > 0, f"File {path} is empty"
