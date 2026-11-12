"""Lançador do MARX SECRET (usado também pelo PyInstaller)."""

import multiprocessing
import sys

from marx_secret.app import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
