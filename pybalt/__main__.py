from asyncio import run
from .core.cobalt import _CobaltDownloadOptions, _CobaltParameters, Cobalt, lprint
from typing import _LiteralGenericAlias
from os.path import exists
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("positional", nargs="?", type=str)
for key, value in {
    **_CobaltDownloadOptions.__annotations__,
    **_CobaltParameters.__annotations__,
}.items():
    try:
        if value not in [bool, str, int, float, _LiteralGenericAlias]:
            continue
        if value is bool:
            if not any(arg.startswith(f"-{key[0]}") for arg in parser._option_string_actions):
                parser.add_argument(
                    f"-{key[0]}{''.join([x for i, x in enumerate(key) if i > 0 and x.isupper()])}",
                    f"--{key}",
                    action="store_true",
                )
            else:
                parser.add_argument(
                    f"-{key[:2].lower()}",
                    f"--{key}",
                    action="store_true",
                )
        else:
            if not any(arg.startswith(f"-{key[0]}") for arg in parser._option_string_actions):
                parser.add_argument(
                    f"-{key[0]}{''.join([x for i, x in enumerate(key) if i > 0 and x.isupper()])}",
                    f"--{key}",
                    type=value,
                    choices=None
                    if not isinstance(value, _LiteralGenericAlias)
                    else value.__args__,
                )
            else:
                parser.add_argument(
                    f"-{key[:2].lower()}",
                    f"--{key}",
                    type=value,
                    choices=None
                    if not isinstance(value, _LiteralGenericAlias)
                    else value.__args__,
                )
    except argparse.ArgumentError:
        parser.add_argument(f"--{key}", type=value)


async def _():
    args = parser.parse_args()
    if args.positional and not args.url:
        args.url = args.positional
    cobalt = Cobalt(
        **{
            key: value
            for key, value in args.__dict__.items()
            if key in _CobaltParameters.__annotations__.keys() and value is not None
        }
    )
    if args.positional and args.remux and exists(args.positional):
        cobalt.remux(args.positional, keep_original=True)
    elif args.remux and not args.url:
        lprint(":red::warning: No URL or FILE PATH provided for remuxing")
    elif args.url:
        if exists(args.url):
            _urls = open(args.url).readlines()
        else:
            _urls = [args.url]
        for url in _urls:
            args.url = url
            await cobalt.download(
                **{
                    key: value
                    for key, value in args.__dict__.items()
                    if key in _CobaltDownloadOptions.__annotations__.keys()
                    and value is not None
                }
            )
        lprint(":sparkles: Thanks for using pybalt, if you enjoyed it please leave a star on GitHub: :accent:https://github.com/nichind/pybalt")
    elif args.updates:
        lprint(":sparkles: pybalt is up to date")
    else:
        lprint(":red::warning: No URL provided")
    
def main():
    run(_())


if __name__ == "__main__":
    main()
