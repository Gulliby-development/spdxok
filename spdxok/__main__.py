import sys

from spdxok.cli import main

sys.stdout.reconfigure(encoding="utf-8", newline="\n")
sys.stderr.reconfigure(encoding="utf-8", newline="\n")
sys.exit(main(sys.argv[1:]))
