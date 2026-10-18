import sys

from spdxok.cli import main


def run() -> None:
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stderr.reconfigure(encoding="utf-8", newline="\n")
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    run()
