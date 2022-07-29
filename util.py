import os
from typing import Dict


file_cache: Dict[str, str] = {}
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

def from_root(file: str) -> str:
    return os.path.join(ROOT_DIR, file)

def load_file(file: str) -> str:
    if file not in file_cache:
        file_cache[file] = open(from_root(file)).read()
    return file_cache[file]
