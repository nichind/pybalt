import argparse
from asyncio import run
from .cobalt import CobaltAPI



async def _():
    parser = argparse.ArgumentParser()
    parser.add_argument('url_arg', nargs='?', type=str, help='URL to download')
    parser.add_argument('-url', '-u', type=str, help='URL to download', required=False)
    parser.add_argument('-list', '-l', type=str, help='Path to file with list of URLs', required=False)
    parser.add_argument('-quality', '-q', '-res', '-r', type=str, help='Video quality to try download', required=False)
    parser.add_argument('-folder', '-f', type=str, help='Path to folder', required=False)
    parser.add_argument('-instance', '-i', type=str, help='Cobalt API instance', required=False)
    parser.add_argument('-key', '-k', type=str, help='API key', required=False)
    parser.add_argument('-playlist', '-pl', type=str, help='Playlist URL (currently YouTube only)', required=False)
    parser.add_argument('-filenameStyle', '-fs', type=str, help='Filename style', required=False)
    parser.add_argument('-audioFormat', '-af', type=str, help='Audio format', required=False)
    parser.add_argument('-youtubeVideoCodec', '-yvc', help='Youtube video codec', required=False)
    parser.add_argument('-v', '-version', help='Display current pybalt version', action='store_true')
    args = parser.parse_args()
    if args.v:
        raise NotImplementedError(f"Not implemented yet")
    if args.url_arg:
        args.url = args.url_arg
    urls = ([args.url] if args.url else []) + ([line.strip() for line in open(args.list)] if args.list else [])
    if not urls and not args.playlist:
        print('No URLs provided', "Use -url 'https://...' or -list 'path/to/txt' or -playlist 'https://...'", sep='\n')
        return
    api = CobaltAPI(api_instance=args.instance, api_key=args.key)
    if args.playlist:
        await api.download(url=args.playlist,
            playlist=True,
            path_folder=args.folder if args.folder else None,
            quality=args.quality if args.quality else '1080',
            filename_style=args.filenameStyle if args.filenameStyle else 'pretty',
            audio_format=args.audioFormat if args.audioFormat else 'mp3',
            youtube_video_codec=args.youtubeVideoCodec if args.youtubeVideoCodec else None
        )
        return
    for url in urls:
        await api.download(url=url,
            path_folder=args.folder if args.folder else None,
            quality=args.quality if args.quality else '1080',
            filename_style=args.filenameStyle if args.filenameStyle else 'pretty',
            audio_format=args.audioFormat if args.audioFormat else 'mp3',
            youtube_video_codec=args.youtubeVideoCodec if args.youtubeVideoCodec else None
        )
    # print('Everything is done! Have a nice day ^w^', 'Consider leaving a star on GitHub: https://github.com/nichind/pybalt', sep='\n')
    
    
def main():
    run(_())


if __name__ == "__main__":
    main()
    