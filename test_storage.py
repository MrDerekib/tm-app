import tempfile
import unittest
from pathlib import Path

from storage import portable_data_directory


class StorageTests(unittest.TestCase):
    def test_source_run_uses_app_folder_instead_of_python_folder(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory).resolve()
            data = portable_data_directory(root / 'project' / 'app.py', root / 'python' / 'python.exe')
            self.assertEqual(data, root / 'project' / 'datos')
            self.assertFalse(data.exists())

    def test_executable_run_uses_exe_folder_instead_of_extracted_resources(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory).resolve()
            data = portable_data_directory(
                root / '_MEI123' / 'app.py', root / 'portable' / 'TM App.exe', frozen=True)
            self.assertEqual(data, root / 'portable' / 'datos')
            self.assertFalse(data.exists())

    def test_moving_executable_changes_data_location(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory).resolve()
            source = root / '_MEI123' / 'app.py'
            first = portable_data_directory(source, root / 'first' / 'TM App.exe', frozen=True)
            second = portable_data_directory(source, root / 'second' / 'TM App.exe', frozen=True)
            self.assertEqual(first, root / 'first' / 'datos')
            self.assertEqual(second, root / 'second' / 'datos')


if __name__ == '__main__':
    unittest.main()
