import pytest
import os

from pybalt import download

YOUTUBE_TEST_LINK = "https://www.youtube.com/watch?v=EFsSYiNl2AQ"
YOUTUBE_TEST_TITLE = "【Ado】ヒバナ 歌いました"
YOUTUBE_TEST_PLAYLIST_LINK = "https://youtube.com/playlist?list=PL_93TBqf4ymT89EVa7UxwpfUH6zrvkKWR&si=6NsPyYDIWARIj0d5"


@pytest.mark.asyncio
async def test_download_youtube():
    # Download the video
    downloaded = await download(YOUTUBE_TEST_LINK, filenameStyle="basic", videoQuality="1080", only_path=False, remux=False)
    path = downloaded[1]

    if downloaded[2] is not None:
        # The exception is not None, report
        raise Exception(f"File {path} was not downloaded correctly: {downloaded[2]}")

    # Check if the file exists
    assert os.path.exists(path), f"File {path} does not exist"

    # Check if filename contains the video title
    assert YOUTUBE_TEST_TITLE in path.name, f"Filename {path} does not contain the video title {YOUTUBE_TEST_TITLE}"

    # Check if the video is in correct resolution
    assert "1080p" in path.name, f"Video resolution {downloaded[0].resolution} is not 1080p"

    # Check if the file is not empty
    assert os.path.getsize(path) > 0, f"File {path} is empty"


@pytest.mark.asyncio
async def test_download_youtube_playlist():
    # Download the playlist
    downloaded = await download(YOUTUBE_TEST_PLAYLIST_LINK, filenameStyle="basic", videoQuality="1080", only_path=False, remux=False)
    
    # Check that we received a list of video results
    assert isinstance(downloaded, list), "Playlist download should return a list of results"
    assert len(downloaded) > 0, "No videos were processed from the playlist"
    
    # Extract paths from successful downloads
    successful_downloads = [(url, path) for url, path, exc in downloaded if path is not None and exc is None]
    
    # Check if we got at least some successful downloads
    assert len(successful_downloads) > 0, "No videos were successfully downloaded from the playlist"
    
    # Log information about successful and failed downloads
    print(f"Successfully downloaded {len(successful_downloads)} out of {len(downloaded)} videos")
    
    # Check specific videos file sizes if they were downloaded
    video_sizes = {
        "9yUzR7_95t0": 104,  # Expected size ~104MB
        "9sA_hDeNxeU": 16.6  # Expected size ~16.6MB
    }
    
    for url, path, exc in downloaded:
        if exc is not None:
            continue
            
        video_id = url.split("=")[-1].split("&")[0]
        
        # Check if the file exists and has content
        assert os.path.exists(path), f"File {path} does not exist"
        assert os.path.getsize(path) > 0, f"File {path} is empty"
        
        size_mb = os.path.getsize(path) / 1024 / 1024
        print(f"Video {video_id} downloaded to {path}, size: {size_mb:.2f}MB")
        
        # Check specific video sizes with 10% tolerance
        if video_id in video_sizes:
            expected_size = video_sizes[video_id]
            tolerance = expected_size * 0.1  # 10% tolerance
            assert abs(size_mb - expected_size) <= tolerance, f"Video {video_id} size {size_mb:.2f}MB differs significantly from expected {expected_size}MB"
