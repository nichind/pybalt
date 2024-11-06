<div align="center" style="display: flex; flex-flow: column wrap;">
  <img src='https://i.imgur.com/IJQgkSJ.png' style='width: 128px'></img>
  <h3>Pybalt</h3>
  <h5>Python module / CLI to download media using cobalt-api instance</h5>
  <br>
  
  [![Get on pypi](https://img.shields.io/pypi/v/pybalt.svg)](https://pypi.org/project/pybalt/)
  [![Last commit](https://img.shields.io/github/last-commit/nichind/pybalt.svg)](https://github.com/nichind/pybalt)
  [![Pip module installs total downloads](https://img.shields.io/pypi/dm/pybalt.svg)](https://pypi.org/project/pybalt/)
  [![GitHub stars](https://img.shields.io/github/stars/nichind/pybalt.svg)](https://github.com/nichind/pybalt)
  
  <br>

  <div align="center" style="display: flex; flex-flow: column wrap;">
  <h3>CLI Preview</h3>
  <img src='./assets/cli-preview.gif'>

  </div>
  
</div>
<br>
<h1>Installation</h1>
<h4>Download using PIP</h4>

```
python -m pip install pybalt
```

<h1>Usage & Examples</h1>
<h3>Inside python file</h3>

```python
from pybalt import Cobalt
from asyncio import run


async def main():
    cobalt = Cobalt(api_key='...', api_instance='https://...')
    print(await cobalt.download("https://www.youtube.com/watch?v=9bZkp7q19f0", quality="1080", path_folder='cute-videos'))


if __name__ == "__main__":
    run(main())
```
<h3>With terminal or cmd</h3>

```bash
pybalt -url 'https://music.youtube.com/watch?v=cxAmzz_tjzc' -folder music -fs pretty
```
<h4>Cli Options:</h4>

```bash
-h, --help            show this help message and exit
-url URL, -u URL      URL to download
-list LIST, -l LIST   Path to file with list of URLs
-quality QUALITY, -q QUALITY, -res QUALITY, -r QUALITY
                      Video quality to try download
-folder FOLDER, -f FOLDER
                      Path to folder
-instance INSTANCE, -i INSTANCE
                      Cobalt API instance
-key KEY, -k KEY      API key
-playlist PLAYLIST, -pl PLAYLIST
                      Playlist URL (currently YouTube only)
-filenameStyle FILENAMESTYLE, -fs FILENAMESTYLE
                      Filename style
-audioFormat AUDIOFORMAT, -af AUDIOFORMAT
                      Audio format
```

Lets say we want to download YouTube playlist in 4k using my instance with api_key, save all videos to folder 'cat-videos', command would look like that:

```bash
pybalt -pl 'playlistUrl' -folder cat-videos -q 4k -i https://dwnld.nichind.dev -k API_KEY
```
