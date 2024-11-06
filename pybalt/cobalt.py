from aiohttp import ClientSession, client_exceptions
from aiofiles import open as aopen
from .exceptions import *
from shutil import get_terminal_size
from re import sub
from os import path, mkdir
from os.path import expanduser
from time import time
from typing import Literal


class File:
    def __init__(self, cobalt = None, status: str = None, url: str = None, filename: str = None, tunnel: str = None) -> None:
        self.cobalt = cobalt
        self.status = status
        self.url = url
        self.tunnel = tunnel
        self.filename = filename
        self.extension = self.filename.split('.')[-1] if self.filename else None
        self.downloaded = False
        self.path = None
    
    async def download(self, path_folder: str = None) -> str:
        self.path = await self.cobalt.download(self.url, self.filename, path_folder, file=self)
        return self.path
    
    def __repr__(self):
        return '<File ' + (self.path if self.path else f'"{self.filename}"') + '>'


class CobaltAPI:
    def __init__(self, 
        api_instance: str = None,
        api_key: str = None,
        headers: dict = None
    ) -> None:
        self.api_instance = f'''{'https://' if "http" not in api_instance else ""}{api_instance}''' if api_instance else 'https://dwnld.nichind.dev'
        self.api_key = api_key
        self.headers = headers
        self.headers = {
            'Accept': 'application/json', 
            'Content-Type': 'application/json',
            'Authorization': f'Api-Key {self.api_key}' if self.api_key else ''
        }

    async def get(self,
        url: str,
        quality: Literal['max', '4320', '2160', '1440', '1080', '720', '480', '360', '240', '144'] = '1080',    
        download_mode: Literal['auto', 'audio', 'mute'] = 'auto',
        filename_style: Literal['classic', 'pretty', 'basic', 'nerdy'] = 'pretty',
        audio_format: Literal['best', 'mp3', 'ogg', 'wav', 'opus'] = None,
        youtube_video_codec: Literal['vp9', 'h264'] = None
    ) -> File:
        async with ClientSession(headers=self.headers) as cs:
            try:
                if quality not in ['max', '3840', '2160', '1440', '1080', '720', '480', '360', '240', '144']:
                    try:
                        quality = {
                            '8k': '3840',
                            '4k': '2160',
                            '2k': '1440',
                            '1080p': '1080',
                            '720p': '720',
                            '480p': '480',
                            '360p': '360',
                            '240p': '240',
                            '144p': '144'
                        }[quality]
                    except:
                        quality = '1080'
                json = {
                    'url': url.replace("'", "").replace('"', '').replace('\\', ''),
                    'videoQuality': quality,
                    'youtubeVideoCodec': youtube_video_codec if youtube_video_codec else 'h264',
                    'filenameStyle': filename_style,
                }
                if audio_format:
                    json['audioFormat'] = audio_format
                # print(json)
                async with cs.post(
                    self.api_instance,
                    json=json
                ) as resp:
                    json = await resp.json()
                    if 'error' in json:
                        match json['error']['code'].split('.')[2]:
                            case 'link':
                                raise LinkError(f'{url} is invalid - {json["error"]["code"]}')
                            case 'content':
                                raise ContentError(f'cannot get content of {url} - {json["error"]["code"]}') 
                            case 'invalid_body':
                                raise InvalidBody(f'Request body is invalid - {json["error"]["code"]}')
                        raise UnrecognizedError(f'{json["error"]["code"]} - {json["error"]}')
                    return File(
                        cobalt=self,
                        status=json['status'],
                        url=url.replace("'", "").replace('"', '').replace('\\', ''),
                        tunnel=json['url'],
                        filename=json['filename']
                    )
            except client_exceptions.ClientConnectorError:
                raise BadInstance(f'Cannot reach instance {self.api_instance}')
         
    async def download(self,
        url: str = None,
        quality: str = None,
        filename: str = None,
        path_folder: str = None,
        download_mode: Literal['auto', 'audio', 'mute'] = 'auto',
        filename_style: Literal['classic', 'pretty', 'basic', 'nerdy'] = 'pretty',
        audio_format: Literal['best', 'mp3', 'ogg', 'wav', 'opus'] = None,
        youtube_video_codec: Literal['vp9', 'h264'] = None,
        playlist: bool = False,
        file: File = None,
    ) -> str:
        """
        Downloads file from url
        
        Parameters:
        url (str): URL to download
        quality (str): Video quality to try download
        filename (str): Filename to save as
        path_folder (str): Folder to save in
        download_mode (Literal['auto', 'audio', 'mute']): Download mode
        filename_style (Literal['classic', 'pretty', 'basic', 'nerdy']): Filename style
        audio_format (Literal['best', 'mp3', 'ogg', 'wav', 'opus']): Audio format
        youtube_video_codec (Literal['vp9', 'h264']): Youtube video codec
        playlist (bool): Whether the url is a playlist
        
        Returns:
        str: Path to saved file
        """
        if playlist:
            from pytube import Playlist
            playlist = Playlist(url)
            for url in playlist:
                print(url)
                await self.download(url,
                    quality=quality,
                    filename=filename,
                    path_folder=path_folder,
                    download_mode=download_mode,
                    filename_style=filename_style,
                    audio_format=audio_format,
                    youtube_video_codec=youtube_video_codec
                    )
            return
        if file is None:
            file = await self.get(
                url,
                quality=quality,
                download_mode=download_mode,
                filename_style=filename_style,
                audio_format=audio_format,
                youtube_video_codec=youtube_video_codec
            )
        if filename is None:
            filename = file.filename
        if path_folder and path_folder[-1] != '/':
            path_folder += '/'
        if path_folder is None:
            path_folder = path.join(expanduser('~'), 'Downloads')
        if not path.exists(path_folder):
            mkdir(path_folder)
        def shorten(s: str, additional_len: int = 0) -> str:
            columns, _ = get_terminal_size()
            free_columns = columns - additional_len - 4
            return s[:free_columns - 3] + '...' if len(s) > free_columns else s
        
        async with ClientSession(headers=self.headers) as session:
            async with aopen(path.join(path_folder, filename), "wb") as f:
                try:
                    progress_chars = ['⢎⡰', '⢎⡡', '⢎⡑', '⢎⠱', '⠎⡱', '⢊⡱', '⢌⡱', '⢆⡱']
                    progress_index = 0
                    total_size = 0
                    start_time = time()
                    last_update = 0
                    downloaded_since_last = 0
                    max_print_length, _ = get_terminal_size()
                    max_print_length -= 2
                    async with session.get(file.tunnel) as response:
                        print(f' \u2015\u2015\u2015 {filename}: ')
                        result_path = path.join(path_folder, f'"{filename}"')
                        while True:
                            chunk = await response.content.read(1024 * 1024)
                            if not chunk:
                                break
                            await f.write(chunk)
                            total_size += len(chunk)
                            downloaded_since_last += len(chunk)
                            if time() - last_update > 0.2:
                                progress_index += 1
                                if progress_index > len(progress_chars) - 1:
                                    progress_index = 0
                                speed = downloaded_since_last / (time() - last_update)
                                speed_display = f'{round(speed / 1024 / 1024, 2)}Mb/s' if speed >= 2 * 1024 * 1024 else f'{round(speed / 1024, 2)}Kb/s'
                                downloaded_since_last = 0
                                last_update = time()
                                info = f'[{round(total_size / 1024 / 1024, 2)}Mb \u2015 {speed_display}] {progress_chars[progress_index]}'
                                print_line = f'{shorten(result_path, additional_len=len(info))}'
                                max_print_length, _ = get_terminal_size()
                                max_print_length -= 2
                                print('\r' + print_line, " " * (max_print_length - len(print_line + ' ' + info)), info, end='')
                    info = f'[{round(total_size / 1024 / 1024, 2)}Mb]  \u2713'
                    print_line = f'{shorten(result_path, additional_len=len(info))}'
                    print('\r', print_line + " " * (max_print_length - len(print_line + info)), info)
                    return path.join(path_folder, filename)
                except client_exceptions.ClientConnectorError:
                    raise BadInstance(f'Cannot reach instance {self.api_instance}')
             
                
Cobalt = CobaltAPI
cobalt = CobaltAPI
Pybalt = CobaltAPI
pybalt = CobaltAPI
