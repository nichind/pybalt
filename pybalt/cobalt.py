from aiohttp import ClientSession, client_exceptions
from .exceptions import *
import os
from typing import Literal


class File:
    def __init__(self, cobalt = None, status: str = None, url: str = None, filename: str = None) -> None:
        self.cobalt = cobalt
        self.status = status
        self.url = url
        self.filename = filename
        self.extension = self.filename.split('.')[-1] if self.filename else None
    
    async def download(self, path_folder: str = None) -> str:
        return await self.cobalt.download(self.url, self.filename, path_folder)
    
    def __repr__(self):
        return f'<File {self.filename}>'


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
            'Authorization': f'Bearer {self.api_key}' if self.api_key else ''
        }

    async def get_file_url(self,
        url: str,
        quality: Literal['max', '4320', '2160', '1440', '1080', '720', '480', '360', '240', '144'] = None,
        download_mode: Literal['auto', 'audio', 'mute'] = 'auto',
        filename_style: Literal['classic', 'pretty', 'basic', 'nerdy'] = 'pretty',
        audio_format: Literal['best', 'mp3', 'ogg', 'wav', 'opus'] = 'mp3'
    ) -> File:
        async with ClientSession(headers=self.headers) as cs:
            try:
                if quality not in ['max', '4320', '2160', '1440', '1080', '720', '480', '360', '240', '144']:
                    try:
                        quality = {
                            '8k': '4320',
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
                async with cs.post(
                    self.api_instance,
                    json={
                        'url': url,
                        'videoQuality': quality,
                        'filenameStyle': filename_style,
                        'downloadMode': download_mode,
                        'audioFormat': audio_format
                    }
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
                        url=json['url'],
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
        audio_format: Literal['best', 'mp3', 'ogg', 'wav', 'opus'] = 'mp3',
        playlist: bool = False
    ) -> str:
        if playlist:
            from pytube import Playlist
            playlist = Playlist(url)
            for url in playlist:
                print(url)
                await self.download(url, quality=quality, filename=filename, path_folder=path_folder, download_mode=download_mode, filename_style=filename_style, audio_format=audio_format)
            return
        file = await self.get_file_url(
            url,
            quality=quality,
            download_mode=download_mode,
            filename_style=filename_style,
            audio_format=audio_format
        )
        if filename is None:
            filename = file.filename
        if path_folder and path_folder[-1] != '/':
            path_folder += '/'
        if path_folder is None:
            path_folder = os.getcwd() + '/Downloads/'
        if not os.path.exists(path_folder):
            os.mkdir(path_folder)
        async with ClientSession(headers=self.headers) as cs:
            with open(path_folder + filename, "wb") as f: 
                print(f'\r{filename}: Downloading to {path_folder}', end='')
                try:
                    async with cs.get(file.url) as response:
                        read = await response.read()
                        f.write(read)
                    print(f'\r{filename}: Downloaded ({round(read.__sizeof__() / 1024 / 1024, 2)}Mb) to {path_folder}{filename}')
                except client_exceptions.ClientConnectorError:
                    raise BadInstance(f'Cannot reach instance {self.api_instance}')
             
                
Cobalt = CobaltAPI
