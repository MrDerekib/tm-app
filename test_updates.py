"""Public release lookup and non-blocking notices, with no network in tests."""
from http.client import IncompleteRead
from io import BytesIO
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import app
from updates import (CACHE_SECONDS, LATEST_RELEASE_API, RELEASES_URL, Release,
                     UpdateError, fetch_latest_release, latest_release, version_tuple)


class UpdateTests(unittest.TestCase):
    def test_numeric_version_comparison_accepts_original_tag(self):
        self.assertEqual(version_tuple('v1.0'), (1, 0, 0))
        self.assertFalse(Release('v1.0').is_newer('1.0.0'))
        self.assertTrue(Release('v1.10.0').is_newer('1.9.0'))
        self.assertFalse(Release('v1.1.0').is_newer('2.0.0'))
        self.assertTrue(Release('v2.0').is_newer('1.99.99'))
        for invalid in (None, 'latest', 'v1.2.0-beta', 'https://example.com', '1.2.3/extra'):
            with self.assertRaises(ValueError):
                Release(invalid)

    def test_public_lookup_and_download_link_stay_in_our_repository(self):
        payload = {'tag_name': 'v1.2.0', 'draft': False, 'prerelease': False,
                   'html_url': 'https://example.com/untrusted'}
        with patch('updates.urlopen', return_value=BytesIO(json.dumps(payload).encode())) as request:
            release = fetch_latest_release()
        self.assertEqual(release.version, '1.2.0')
        self.assertEqual(release.url, RELEASES_URL + '/tag/v1.2.0')
        argument = request.call_args.args[0]
        self.assertEqual(argument.full_url, LATEST_RELEASE_API)
        self.assertNotIn('Authorization', argument.headers)
        self.assertEqual(request.call_args.kwargs['timeout'], 6)

    def test_drafts_and_prereleases_are_not_offered(self):
        for flag in ('draft', 'prerelease'):
            with patch('updates.urlopen', return_value=BytesIO(json.dumps({'tag_name': 'v9.0.0', flag: True}).encode())):
                self.assertIsNone(fetch_latest_release())

    def test_http_and_transport_errors_become_readable_results(self):
        with patch('updates.urlopen', side_effect=HTTPError(LATEST_RELEASE_API, 404, 'Missing', {}, None)):
            self.assertIsNone(fetch_latest_release())
        for error in (HTTPError(LATEST_RELEASE_API, 403, 'Limited', {}, None),
                      HTTPError(LATEST_RELEASE_API, 429, 'Limited', {}, None),
                      HTTPError(LATEST_RELEASE_API, 500, 'Server', {}, None),
                      URLError('Offline'), TimeoutError(), IncompleteRead(b'partial', 10)):
            with self.subTest(error=type(error).__name__), patch('updates.urlopen', side_effect=error):
                with self.assertRaises(UpdateError):
                    fetch_latest_release()

    def test_malformed_replies_are_rejected(self):
        for raw in (b'invalid json', b'[]', b'{}', b'{"tag_name":"v2.0-beta"}'):
            with patch('updates.urlopen', return_value=BytesIO(raw)):
                with self.assertRaises(UpdateError):
                    fetch_latest_release()

    def test_daily_cache_manual_refresh_and_expiry(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path = Path(directory) / 'updates.json'
            with patch('updates.time.time', return_value=1000), patch('updates.fetch_latest_release', return_value=Release('v1.0')) as fetch:
                self.assertEqual(latest_release(path).tag, 'v1.0')
                fetch.assert_called_once()
            with patch('updates.time.time', return_value=1100), patch('updates.fetch_latest_release') as fetch:
                self.assertEqual(latest_release(path).tag, 'v1.0')
                fetch.assert_not_called()
            with patch('updates.time.time', return_value=1200), patch('updates.fetch_latest_release', return_value=Release('v1.1.0')) as fetch:
                self.assertEqual(latest_release(path, force=True).tag, 'v1.1.0')
                fetch.assert_called_once()
            with patch('updates.time.time', return_value=1200 + CACHE_SECONDS), \
                 patch('updates.fetch_latest_release', return_value=Release('v1.2.0')) as fetch:
                self.assertEqual(latest_release(path).tag, 'v1.2.0')
                fetch.assert_called_once()

    def test_cache_problems_do_not_hide_a_valid_online_result(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path = Path(directory) / 'updates.json'
            for contents in ('invalid', '[]', '{"format":1,"checked_at":"bad"}'):
                path.write_text(contents, encoding='utf-8')
                with patch('updates.fetch_latest_release', return_value=Release('v1.2.0')) as fetch:
                    self.assertEqual(latest_release(path).tag, 'v1.2.0')
                    fetch.assert_called_once()
            with patch('updates.fetch_latest_release', return_value=Release('v1.2.0')):
                self.assertEqual(latest_release(Path(directory) / 'missing' / 'updates.json').tag, 'v1.2.0')

    def test_cached_absence_and_profile_files_are_preserved(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            for name in ('machines.json', 'appearance.json'):
                (root / name).write_bytes(b'preserve existing user data')
            with patch('updates.fetch_latest_release', return_value=None):
                self.assertIsNone(latest_release(root / 'updates.json'))
            with patch('updates.fetch_latest_release') as fetch:
                self.assertIsNone(latest_release(root / 'updates.json'))
                fetch.assert_not_called()
            for name in ('machines.json', 'appearance.json'):
                self.assertEqual((root / name).read_bytes(), b'preserve existing user data')


class UpdateWindowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.directory.cleanup)
        self.data = patch.object(app, 'DATA', Path(self.directory.name) / 'datos')
        self.data.start()
        self.addCleanup(self.data.stop)
        self.gui = app.App(check_updates=False)
        self.gui.update()
        self.addCleanup(self.destroy_gui)

    def destroy_gui(self):
        self.gui.update_idletasks()
        for job in self.gui.tk.call('after', 'info'):
            self.gui.after_cancel(job)
        self.gui.destroy()

    def test_new_release_banner_and_click_do_not_touch_serial_state(self):
        before = self.gui.profile_path.read_bytes()
        self.gui.session += 10
        self.gui.busy = True
        self.gui.update_results.put((False, Release('v99.0.0'), None))
        with patch('app.messagebox.showinfo') as message, patch('app.webbrowser.open') as browser:
            self.gui.poll_updates()
            self.gui.update()
            message.assert_not_called()
            browser.assert_not_called()
            self.gui.open_update_page()
            browser.assert_called_once_with(RELEASES_URL + '/tag/v99.0.0')
        self.assertEqual(self.gui.update_banner.winfo_manager(), 'pack')
        self.assertTrue(self.gui.busy)
        self.assertEqual(self.gui.profile_path.read_bytes(), before)
        self.gui.geometry('900x600')
        self.gui.update()
        self.assertTrue(self.gui.manual.winfo_ismapped())
        self.assertTrue(self.gui.run_btn.winfo_ismapped())
        self.gui.busy = False

    def test_automatic_failures_are_quiet_manual_checks_report_errors(self):
        with patch('app.messagebox.showinfo') as message:
            self.gui.update_results.put((False, None, 'Sin conexión'))
            self.gui.poll_updates()
            message.assert_not_called()
            self.gui.update_results.put((True, None, 'Sin conexión'))
            self.gui.poll_updates()
            message.assert_called_once()
        self.assertFalse(self.gui.update_in_progress)
        self.assertEqual(self.gui.help_menu.entrycget(0, 'state'), 'normal')

    def test_current_or_older_versions_do_not_show_an_update_banner(self):
        for manual in (False, True):
            with patch('app.messagebox.showinfo') as message:
                self.gui.update_results.put((manual, Release('v1.0'), None))
                self.gui.poll_updates()
                self.assertEqual(self.gui.update_banner.winfo_manager(), '')
                self.assertIsNone(self.gui.available_release)
                self.assertEqual(message.call_count, int(manual))

    def test_background_lookup_does_not_block_ui_or_duplicate_requests(self):
        started, finish = threading.Event(), threading.Event()
        self.addCleanup(finish.set)

        def fetch(*args, **kwargs):
            started.set()
            if not finish.wait(2):
                raise UpdateError('Test timeout')
            return Release('v99.0.0')

        with patch('app.latest_release', side_effect=fetch) as lookup:
            self.gui.check_for_updates(manual=True)
            self.assertTrue(started.wait(1))
            self.gui.update()
            self.assertTrue(self.gui.update_in_progress)
            self.assertEqual(self.gui.help_menu.entrycget(0, 'state'), 'disabled')
            self.gui.check_for_updates(manual=True)
            finish.set()
            deadline = time.monotonic() + 2
            while self.gui.update_in_progress and time.monotonic() < deadline:
                self.gui.update()
                time.sleep(0.01)
            self.assertFalse(self.gui.update_in_progress)
            lookup.assert_called_once_with(app.DATA / 'updates.json', force=True)
        self.assertEqual(self.gui.available_release.tag, 'v99.0.0')


if __name__ == '__main__':
    unittest.main()
