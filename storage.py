"""Locate portable user data independently of bundled application resources."""
from pathlib import Path


def portable_data_directory(source_file, executable, *, frozen=False):
    application_file = executable if frozen else source_file
    return Path(application_file).resolve().parent / 'datos'
