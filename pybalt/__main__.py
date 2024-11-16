import argparse
from asyncio import run
from .cobalt import Cobalt, check_updates
from os import path
from time import time
from importlib.metadata import version


async def _():
    parser = argparse.ArgumentParser()
    parser.add_argument("url_arg", nargs="?", type=str, help="URL to download")
    parser.add_argument("-url", "-u", type=str, help="URL to download", required=False)
    parser.add_argument(
        "-list", "-l", type=str, help="Path to file with list of URLs", required=False
    )
    parser.add_argument(
        "-quality",
        "-q",
        "-res",
        "-r",
        type=str,
        help="Video quality to try download",
        required=False,
    )
    parser.add_argument(
        "-folder", "-f", type=str, help="Path to folder", required=False
    )
    parser.add_argument(
        "-instance", "-i", type=str, help="Cobalt API instance", required=False
    )
    parser.add_argument("-key", "-k", type=str, help="API key", required=False)
    parser.add_argument(
        "-playlist",
        "-pl",
        type=str,
        help="Playlist URL (currently YouTube only)",
        required=False,
    )
    parser.add_argument(
        "-filenameStyle",
        "-fs",
        type=str,
        help="Filename style",
        required=False,
        choices=["classic", "pretty", "basic", "nerdy"],
    )
    parser.add_argument(
        "-audioFormat",
        "-af",
        type=str,
        help="Audio format",
        required=False,
        choices=["mp3", "ogg", "wav", "opus"],
    )
    parser.add_argument(
        "-youtubeVideoCodec",
        "-yvc",
        help="Youtube video codec",
        required=False,
        choices=["vp9", "h264"],
    )
    parser.add_argument(
        "-show",
        "-s",
        help="Show media in file manager after download",
        action="store_true",
    )
    parser.add_argument(
        "-play", "-p", help="Play media after download", action="store_true"
    )
    parser.add_argument(
        "-v", "-version", help="Display current pybalt version", action="store_true"
    )
    parser.add_argument("-up", "-update", help="Check for updates", action="store_true")
    args = parser.parse_args()
    if args.v:
        try:
            print(f"pybalt {version('pybalt')}")
        except Exception:
            print("Failed to get pybalt version. Running from dev?")
        return
    if args.up:
        await check_updates()
        return
    if args.url_arg:
        args.url = args.url_arg
    urls = ([args.url] if args.url else []) + (
        [line.strip() for line in open(args.list)] if args.list else []
    )
    if args.url and not path.isdir(args.url) and path.isfile(args.url):
        urls = [
            line.strip() for line in open(args.url_arg if args.url_arg else args.url)
        ]
    if not urls and not args.playlist:
        print(
            "No URLs provided",
            "Expected media url, path to file with list of URLs or youtube playlist link",
            "Example: cobalt 'https://youtube.com/watch?...' -s",
            sep="\n",
        )
        return
    api = Cobalt(api_instance=args.instance, api_key=args.key)
    if args.playlist:
        await api.download(
            url=args.playlist,
            playlist=True,
            path_folder=args.folder if args.folder else None,
            quality=args.quality if args.quality else "1080",
            filename_style=args.filenameStyle if args.filenameStyle else "pretty",
            audio_format=args.audioFormat if args.audioFormat else "mp3",
            youtube_video_codec=args.youtubeVideoCodec
            if args.youtubeVideoCodec
            else None,
            show=args.show,
            play=args.play,
        )
        return
    for url in urls:
        await api.download(
            url=url,
            path_folder=args.folder if args.folder else None,
            quality=args.quality if args.quality else "1080",
            filename_style=args.filenameStyle if args.filenameStyle else "pretty",
            audio_format=args.audioFormat if args.audioFormat else "mp3",
            youtube_video_codec=args.youtubeVideoCodec
            if args.youtubeVideoCodec
            else None,
            show=args.show,
            play=args.play,
        )
    print(
        "\033[92mEverything Done!\033[0m Thanks for using pybalt! Leave a star on GitHub: https://github.com/nichind/pybalt"
    )


def main():
    update_check_file = path.expanduser("~/.pybalt")
    if not path.exists(update_check_file):
        with open(update_check_file, "w") as f:
            f.write("0")
    with open(update_check_file) as f:
        if int(f.read()) < int(time()) - 60 * 60:
            print("Checking for updates...", flush=True)
            run(check_updates())
            with open(update_check_file, "w") as f:
                f.write(str(int(time())))
            print("\r", end="")
    run(_())


if __name__ == "__main__":
    main()
