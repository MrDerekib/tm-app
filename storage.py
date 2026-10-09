"""Preserve user profiles and preferences when moving to TM App's data folder."""
import shutil
import tempfile
from pathlib import Path


def migrate_user_data(destination, legacy):
    destination, legacy = Path(destination), Path(legacy)
    destination.mkdir(parents=True, exist_ok=True)
    for name in ('machines.json', 'machines.backup.json', 'appearance.json', 'preferences.json'):
        source, target = legacy / name, destination / name
        if target.exists() or not source.is_file():
            continue
        with tempfile.NamedTemporaryFile(dir=destination, prefix='.migration-', delete=False) as file:
            temporary = Path(file.name)
        try:
            shutil.copyfile(source, temporary)
            if not target.exists():
                temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
