from asyncio import run
from .core.cobalt import _CobaltDownloadOptions, _CobaltParameters, Cobalt
from typing import _LiteralGenericAlias
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("positional", nargs="?", type=str)
for key, value in _CobaltDownloadOptions.__annotations__.items():
    try:
        parser.add_argument(
            f"-{key[0]}{''.join([x if x.isupper() or (i > 0 and key[i-1] == '_') else '' for i, x in enumerate(key)])}",
            f"--{key}",
            type=value,
            choices=None if not isinstance(value, _LiteralGenericAlias) else value.__args__,
        )
    except argparse.ArgumentError:
        parser.add_argument(f"--{key}", type=value)
for key, value in _CobaltParameters.__annotations__.items():
    try:
        parser.add_argument(f"--{key}", type=value)
    except Exception:
        pass

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
    await cobalt.download(
        **{
            key: value
            for key, value in args.__dict__.items()
            if key in _CobaltDownloadOptions.__annotations__.keys()
            and value is not None
        }
    )


def main():
    run(_())


if __name__ == "__main__":
    main()
