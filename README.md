<div align="center" style="display: flex; flex-flow: column wrap;">
  <img src='./assets/logo.png' style='border-radius: 8px; width: 124px'></img>
  <h3>pybalt</h3>
  <h5>Python module and CLI tool for downloading media through Cobalt processing instances.</h5>
  <br>

  [![GitHub stars](https://img.shields.io/github/stars/nichind/pybalt.svg)](https://github.com/nichind/pybalt)
  [![Get on pypi](https://img.shields.io/pypi/v/pybalt.svg)](https://pypi.org/project/pybalt/)
  [![Last commit](https://img.shields.io/github/last-commit/nichind/pybalt.svg)](https://github.com/nichind/pybalt)
  [![Pip module installs total downloads](https://img.shields.io/pypi/dm/pybalt.svg)](https://pypi.org/project/pybalt/)
  [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
  
  <div align="center" style="display: flex; flex-flow: column wrap;">
  <h3>CLI Preview</h3>
  <video src='./assets/preview.mp4' controls>
  </div>
  
</div>
<br><br>
<h1>Installation</h1>
<h4>Install using PowerShell</h4>

```powershell
powershell -Command "Invoke-WebRequest -Uri https://raw.githubusercontent.com/nichind/pybalt/main/install.bat -OutFile install.bat; .\install.bat"
```

<h4>Install using PIP</h4>

```shell
pip install pybalt
```  

This should create aliases `pybalt` and `cobalt` in your shell.

Try running `cobalt -h` to see the help message.

If for some reason it didn't work, try using it with python:

```shell
python -m pybalt
```
<br><br>
<h1>Usage & Examples</h1>

<img src='./assets/cli-preview.gif' style='border-radius: 8px'></img>

<h3>Selecting processing instance</h3>

You can set **processing instance url**, **api key** and **user-agent** to enviroment variables, pybalt will use them if none was provided.


```
COBALT_API_URL=YOUR_INSTANCE_URL
COBALT_API_KEY=YOUR_API_KEY
COBALT_USER_AGENT=YOUR_USER_AGENT
```

By default pybalt tries to parse any avalible instance for you. I recommend hosting your own instance or asking someone to give you `api key` for their instance.

<br>
<h2>As a CLI</h2>
<details open>
<summary></summary>

Every command here uses the `cobalt` alias, you can also use `pybalt` or `python -m pybalt` as well.

By default all downloads are saved in a user downloads folder `~/Downloads` or the one specified by the `--folder` flag.

Get list of all available commands by running:

```shell
cobalt -h
```

<br>
<h3>Download video from URL</h3>

```shell
cobalt -u 'https://youtube.com/watch?v=8ZP5eqm4JqM'
```

you can also provide url as positional argument:

```shell
cobalt 'https://youtube.com/watch?v=8ZP5eqm4JqM'
```

<br>
<h3>Download Youtube playlist</h3>

```shell
cobalt -pl 'https://youtube.com/playlist?list=PL_93TBqf4ymR9GsuI9W4kQ-G3WM7d2Tqj'
```

<br>
<h3>Download from text file</h3>

Create a text file with URLs on each line:

```txt
https://youtube.com/watch?v=8ZP...
.....
....
...
```

then run:

```shell
cobalt -l 'path/to/file.txt'
```

<br>
<h3>More examples</h3>

Download all videos from a YouTube playlist in `720p` to folder `/Music/`, filename style `classic`, use instance `https://dwnld.nichind.dev` with `api key` authorization

```shell
cobalt -pl 'https://youtube.com/playlist?list=PL_93TBqf4ymR9GsuI9W4kQ-G3WM7d2Tqj' -q 720 -f './Music/' -fs 'classic' -i 'https://dwnld.nichind.dev' -k 'YOUR_API_KEY'
```

</details>
<br><br>
<h2>As a module</h2>

<details open>

<h3>Download video from URL</h3>

```python
from pybalt import Cobalt
from asyncio import run


async def main():
    cobalt = Cobalt()
    path = await cobalt.download('https://youtube.com/watch?v=8ZP5eqm4JqM')
    print('Downloaded: ', path)  # Downloaded: /Users/%USER%/Downloads/8ZP5eqm4JqM.mp4


run(main())
```

You can pass arguments inside Cobalt object:

```python
from pybalt import Cobalt
from asyncio import run


async def main():
    cobalt = Cobalt(api_instance='YOUR_INSTANCE_URL', api_key='YOUR_API_KEY', headers={...})
    path = await cobalt.download(url='https://youtube.com/watch?v=8ZP5eqm4JqM', quality='1080')
    print('Downloaded: ', path)  # Downloaded: /Users/%USER%/Downloads/8ZP5eqm4JqM.mp4


run(main())
``` 

</details>

<br><br>
<h1>Contributing</h1>

If you have any questions or suggestions, please [open an issue](https://github.com/nichind/pybalt/issues) or [create a pull request](https://github.com/nichind/pybalt/pulls).

<h3>Contributors</h3>

<img src="https://contrib.rocks/image?repo=nichind/pybalt" alt="Contributors" style="max-width: 100%;"/>
