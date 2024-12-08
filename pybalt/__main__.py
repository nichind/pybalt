import argparse
from asyncio import run
from .cobalt import Cobalt, check_updates, tl
from os import path
from time import time
from importlib.metadata import version


async def _():
    parser = argparse.ArgumentParser()
    parser.add_argument("url_arg", nargs="?", type=str, help=tl("URL_ARGUMENT"))
    parser.add_argument(
        "-u", "--url", type=str, help=tl("URL_ARGUMENT"), required=False
    )
    parser.add_argument(
        "-l", "--list", type=str, help=tl("FILE_ARGUMENT"), required=False
    )
    parser.add_argument(
        "-q",
        "-r",
        "--quality",
        "--resolution",
        type=str,
        help=tl("QUALITY_ARGUMENT"),
        required=False,
    )
    parser.add_argument(
        "-f", "--folder", type=str, help=tl("FOLDER_ARGUMENT"), required=False
    )
    parser.add_argument(
        "-i", "--instance", type=str, help=tl("INSTANCE_ARGUMENT"), required=False
    )
    parser.add_argument(
        "-k", "--key", type=str, help=tl("APIKEY_ARGUMENT"), required=False
    )
    parser.add_argument(
        "-pl",
        "--playlist",
        type=str,
        help=tl("PLAYLIST_ARGUMENT"),
        required=False,
    )
    parser.add_argument(
        "-fs",
        "--filenameStyle",
        type=str,
        help=tl("FILENAME_ARGUMENT"),
        required=False,
        choices=["classic", "pretty", "basic", "nerdy"],
    )
    parser.add_argument(
        "-af",
        "--audioFormat",
        type=str,
        help=tl("AUDIO_ARGUMENT"),
        required=False,
        choices=["mp3", "ogg", "wav", "opus"],
    )
    parser.add_argument(
        "-yvc",
        "--youtubeVideoCodec",
        help=tl("YOUTUBE_VIDEO_CODEC_ARGUMENT"),
        required=False,
        choices=["vp9", "h264"],
    )
    parser.add_argument(
        "-s",
        "--show",
        help=tl("SHOW_ARGUMENT"),
        action="store_true",
    )
    parser.add_argument("-play", "-p", help=tl("PLAY_ARGUMENT"), action="store_true")
    parser.add_argument(
        "-v", "--version", help=tl("VERSION_ARGUMENT"), action="store_true"
    )
    parser.add_argument(
        "-up", "--update", help=tl("UPDATE_ARGUMENT"), action="store_true"
    )
    args = parser.parse_args()
    if args.version:
        try:
            print(tl("VERSION").format(version("pybalt")))
        except Exception:
            print(tl("PACKAGE_NOT_FOUND"))
        return
    if args.update:
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
            tl("NO_URL_PROVIDED"),
            sep="\n",
        )
        return
    api = Cobalt(api_instance=args.instance, api_key=args.key)
    if args.playlist:
        urls += [args.playlist]
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
    print(tl("SUCCESS"))


def main():
    update_check_file = path.expanduser("~/.pybalt")
    if not path.exists(update_check_file):
        with open(update_check_file, "w") as f:
            f.write("0")
    with open(update_check_file) as f:
        if int(f.read()) < int(time()) - 60 * 60:
            print(tl("CHECKING_FOR_UPDATES"), flush=True)
            run(check_updates())
            with open(update_check_file, "w") as f:
                f.write(str(int(time())))
            print("\r", end="")
    run(_())


if __name__ == "__main__":
    main()
