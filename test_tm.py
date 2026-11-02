"""Captured physical TM bytes and receive-only UI behavior, without hardware."""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

import serial
from tm_test import KEY_ROWS, TMKeyState, TMTestWindow


# Actual capture: ESC twice, special keys, then digits, S and N.
CAPTURE = bytes.fromhex('1B 1B 46 0D 24 B2 B4 B8 B6 31 32 33 34 35 36 37 38 39 30 53 4E')
EXPECTED = ['ESC', 'ESC', 'F1', 'CR', 'A', '↑', '←', '↓', '→', *'1234567890SN']


class TMKeyTests(unittest.TestCase):
    def test_real_capture_identifies_all_twenty_keys_and_repetitions(self):
        state = TMKeyState()
        self.assertEqual([key for key, _ in state.feed(CAPTURE)], EXPECTED)
        self.assertEqual(set(state.counts), {key for row in KEY_ROWS for key in row})
        self.assertEqual(state.counts['ESC'], 2)
        self.assertEqual(sum(state.counts.values()), 21)
        self.assertFalse(state.unknown)

    def test_fragmented_reads_and_unknown_bytes_preserve_each_event(self):
        state = TMKeyState()
        events = []
        for byte in CAPTURE:
            events.extend(state.feed(bytes((byte,))))
        self.assertEqual([key for key, _ in events], EXPECTED)
        self.assertEqual(state.feed(b'\x00\xff'), [(None, 0), (None, 255)])
        self.assertEqual(dict(state.unknown), {0: 1, 255: 1})
        self.assertEqual(len(state.counts), 20)


class ReceiveOnlyTransport:
    def __init__(self, data=CAPTURE):
        self.buffer = bytearray(data)
        self.closed = False

    @property
    def in_waiting(self):
        return len(self.buffer)

    def read(self, size):
        data = bytes(self.buffer[:size])
        del self.buffer[:size]
        return data

    def write(self, data):
        raise AssertionError('TM keyboard testing must never transmit')

    def reset_input_buffer(self):
        raise AssertionError('Do not discard the first physical keypress')

    def close(self):
        self.closed = True


class TMWindowTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.window = TMTestWindow(self.root)
        self.root.update()

    def tearDown(self):
        if self.window.winfo_exists():
            self.window.close()
        self.root.update_idletasks()
        for job in self.root.tk.call('after', 'info'):
            self.root.after_cancel(job)
        self.root.destroy()

    def poll_once(self):
        self.window.after_cancel(self.window.poll_job)
        self.window.poll_job = None
        self.window.poll()

    def test_receive_only_connection_highlights_counts_and_preserves_log_on_disconnect(self):
        transport = ReceiveOnlyTransport(CAPTURE + b'\xff')
        with patch('tm_test.serial.Serial', return_value=transport) as serial_factory:
            self.window.toggle_connection()
        serial_factory.assert_called_once_with('COM1', baudrate=2400, bytesize=8, parity='N', stopbits=1.0,
                                               timeout=0, xonxoff=False, rtscts=False, dsrdtr=False)
        self.poll_once()
        self.assertIn('20/20', self.window.summary.cget('text'))
        self.assertIn('1 códigos desconocidos', self.window.summary.cget('text'))
        self.assertEqual(self.window.key_labels['ESC'].cget('text'), 'ESC\n2')
        self.assertEqual(self.window.key_labels['A'].cget('text'), 'A\n1')
        self.assertEqual(self.window.key_labels['↑'].cget('text'), '↑\n1')
        self.assertIn('HEX FF', self.window.latest.cget('text'))
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            output = Path(directory) / 'tm.txt'
            with patch('tm_test.filedialog.asksaveasfilename', return_value=str(output)):
                self.window.save_log()
            log = output.read_text(encoding='utf-8')
            self.assertIn('HEX B2', log)
            self.assertIn("b'\\r'", log)
            self.assertNotIn('TX', log)
        self.window.disconnect()
        self.assertTrue(transport.closed)
        self.assertIsNone(self.window.poll_job)
        self.assertEqual(len(self.window.key_state.counts), 20)
        self.assertTrue(self.window.history)

    def test_reset_clears_test_without_transmitting_or_disconnect(self):
        transport = ReceiveOnlyTransport()
        with patch('tm_test.serial.Serial', return_value=transport):
            self.window.toggle_connection()
        self.poll_once()
        self.window.reset_test()
        self.assertIs(self.window.transport, transport)
        self.assertFalse(transport.closed)
        self.assertFalse(self.window.key_state.counts)
        self.assertFalse(self.window.history)
        self.assertEqual(self.window.key_labels['ESC'].cget('text'), 'ESC\n0')

    def test_connection_error_and_read_error_leave_port_closed_and_keep_results(self):
        with patch('tm_test.serial.Serial', side_effect=serial.SerialException('Test port busy')), \
             patch('tm_test.messagebox.showerror') as error:
            self.window.toggle_connection()
            error.assert_called_once()
        self.assertIsNone(self.window.transport)
        self.assertIsNone(self.window.poll_job)
        self.window.receive(b'1')
        transport = ReceiveOnlyTransport()
        with patch('tm_test.serial.Serial', return_value=transport):
            self.window.toggle_connection()
        with patch.object(transport, 'read', side_effect=serial.SerialException('Test disconnect')):
            self.poll_once()
        self.assertTrue(transport.closed)
        self.assertIsNone(self.window.transport)
        self.assertIsNone(self.window.poll_job)
        self.assertEqual(self.window.key_state.counts['1'], 1)
        self.assertIn('Error de recepción', self.window.status.cget('text'))

    def test_invalid_settings_do_not_open_port(self):
        self.window.fields['baudrate'].set('-1')
        with patch('tm_test.serial.Serial') as serial_factory, patch('tm_test.messagebox.showerror') as error:
            self.window.toggle_connection()
        serial_factory.assert_not_called()
        error.assert_called_once()


if __name__ == '__main__':
    unittest.main()
