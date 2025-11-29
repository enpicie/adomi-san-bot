import sys
import os
import time
from pathlib import Path

import requests

# --- Add src/ to sys.path so we can import command_map ---
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
sys.path.append(str(SRC_DIR))

from commands.command_map import command_map

def main():
    for name, entry in command_map.items():
        print(name)

if __name__ == "__main__":
    main()
