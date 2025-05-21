import pytest
import os
from pybalt import Cobalt


TWITTER_TEST_URL = "https://x.com/oicolatcho/status/1922627222998827203"


@pytest.mark.asyncio
async def test_old_codestyle():
    cobalt = Cobalt()
    path = await cobalt.download(TWITTER_TEST_URL, filenameStyle="pretty", remux=True, youtubeHLS=False, videoQuality="1080")
    assert os.path.exists(path), f"File {path} does not exist"
    assert os.path.getsize(path) > 0, f"File {path} is empty"
