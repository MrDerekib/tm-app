import tempfile
import unittest
from pathlib import Path

from storage import migrate_user_data


class StorageTests(unittest.TestCase):
    def test_migration_preserves_user_data_and_originals(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            legacy, destination = root / 'previous', root / 'TM App'
            legacy.mkdir()
            files = ('machines.json', 'machines.backup.json', 'appearance.json', 'preferences.json')
            for name in files:
                (legacy / name).write_text('{"saved": "' + name + '"}', encoding='utf-8')
            (legacy / 'unrelated.txt').write_text('unrelated', encoding='utf-8')
            migrate_user_data(destination, legacy)
            for name in files:
                self.assertEqual((destination / name).read_bytes(), (legacy / name).read_bytes())
            self.assertEqual({path.name for path in destination.iterdir()}, set(files))
            (destination / 'machines.json').write_text('{"newer": true}', encoding='utf-8')
            migrate_user_data(destination, legacy)
            self.assertEqual((destination / 'machines.json').read_text(encoding='utf-8'), '{"newer": true}')

    def test_fresh_install_does_not_create_default_profiles_during_migration(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            destination = root / 'TM App'
            migrate_user_data(destination, root / 'missing')
            self.assertTrue(destination.is_dir())
            self.assertEqual(list(destination.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
