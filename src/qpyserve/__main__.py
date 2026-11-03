"""Allow `python -m qpyserve` as well as the `qpyserve` console script."""

from ._cli import main

if __name__ == "__main__":
    raise SystemExit(main())
