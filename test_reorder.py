"""Exercise real Tk mouse events with isolated profiles and no serial connection."""
import copy
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app
from core import read_profile


class ReorderTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.directory.cleanup)
        self.data = patch.object(app, 'DATA', Path(self.directory.name) / 'datos')
        self.data.start()
        self.addCleanup(self.data.stop)
        self.gui = app.App(check_updates=False)
        self.addCleanup(self.destroy_gui, self.gui)
        self.gui.geometry('1120x740+80+80')
        profiles = copy.deepcopy(self.gui.profiles)
        profiles['machines'].append(dict(copy.deepcopy(profiles['machines'][0]), name='Otro equipo'))
        self.gui.store_profiles(profiles, profiles['machines'][0]['name'])
        self.gui.update()
        self.original = copy.deepcopy(profiles)
        self.clock = 1000

    def destroy_gui(self, gui):
        gui.update_idletasks()
        for job in gui.tk.call('after', 'info'):
            gui.after_cancel(job)
        gui.destroy()

    def point(self, widget, index):
        widget.see(index)
        self.gui.update()
        bounds = widget.bbox(index)
        self.assertIsNotNone(bounds)
        return 30, bounds[1] + bounds[3] // 2

    def emit(self, widget, event, x, y, when):
        widget.event_generate(event, x=x, y=y, time=when)
        self.gui.update()

    def drag(self, widget, source, target):
        x, y = self.point(widget, source)
        self.clock += 2000
        self.emit(widget, '<ButtonPress-1>', x, y, self.clock)
        target_bounds = widget.bbox(target)
        self.assertIsNotNone(target_bounds)
        target_y = target_bounds[1] + target_bounds[3] // 2
        self.emit(widget, '<B1-Motion>', x, target_y, self.clock + 50)
        self.emit(widget, '<ButtonRelease-1>', x, target_y, self.clock + 100)

    def test_main_reorder_persists_without_sending_commands_or_resetting_connection_fields(self):
        operations = copy.deepcopy(self.original['machines'][0]['operations'])
        expected = operations[1:3] + operations[:1] + operations[3:]
        self.gui.port.set('COM88')
        with patch.object(self.gui, 'execute') as execute:
            self.drag(self.gui.ops, 0, 2)
            execute.assert_not_called()
            # A double-release directly after a drop must not execute the moved action.
            x, y = self.point(self.gui.ops, 2)
            self.gui.ops_reorder.double_release(SimpleNamespace(x=x, y=y))
            execute.assert_not_called()
        saved = read_profile(self.gui.profile_path)
        self.assertEqual(saved['machines'][0]['operations'], expected)
        self.assertEqual(saved['machines'][1], self.original['machines'][1])
        self.assertEqual(self.gui.ops.get(0, 'end'), tuple(op['name'] for op in expected))
        self.assertEqual(self.gui.ops.curselection(), (2,))
        self.assertEqual(self.gui.port.get(), 'COM88')
        self.assertEqual(saved['machines'][0]['connection'], self.original['machines'][0]['connection'])
        self.drag(self.gui.ops, 2, 0)
        self.assertEqual(read_profile(self.gui.profile_path), self.original)

    def test_drag_feedback_shows_name_destination_cursor_and_saved_result(self):
        widget = self.gui.ops
        source_name = widget.get(0)
        x, y = self.point(widget, 0)
        self.emit(widget, '<Motion>', x, y, 2000)
        self.assertEqual(str(widget.cget('cursor')), 'hand2')
        self.emit(widget, '<ButtonPress-1>', x, y, 3000)
        bounds = widget.bbox(2)
        target_y = bounds[1] + bounds[3] // 2
        self.emit(widget, '<B1-Motion>', x, target_y, 3050)
        helper = self.gui.ops_reorder
        self.assertEqual(str(widget.cget('cursor')), 'sb_v_double_arrow')
        self.assertTrue(helper.marker.winfo_ismapped())
        self.assertEqual(helper.marker.winfo_height(), 4)
        self.assertTrue(helper.ghost.winfo_ismapped())
        self.assertIn(source_name, helper.ghost.cget('text'))
        self.assertIn('Posición 3', helper.ghost.cget('text'))
        self.assertIn('Esc cancela', self.gui.reorder_hint.get())
        self.emit(widget, '<ButtonRelease-1>', x, target_y, 3100)
        self.assertIsNone(helper.ghost)
        self.assertFalse(helper.marker.winfo_ismapped())
        self.assertIn('Orden guardado', self.gui.reorder_hint.get())
        self.assertEqual(str(widget.cget('cursor')), 'hand2')

    def test_escape_cancels_drag_and_removes_its_visuals_without_executing(self):
        widget = self.gui.ops
        helper = self.gui.ops_reorder
        before = self.gui.profile_path.read_bytes()
        x, y = self.point(widget, 0)
        widget.focus_force()
        self.gui.update()
        self.emit(widget, '<ButtonPress-1>', x, y, 3000)
        target_y = widget.bbox(2)[1] + 4
        self.emit(widget, '<B1-Motion>', x, target_y, 3050)
        self.assertTrue(helper.dragging)
        self.emit(widget, '<Escape>', x, target_y, 3070)
        self.assertIsNone(helper.ghost)
        self.assertTrue(helper.cancelled)
        self.assertIn('cancelada', self.gui.reorder_hint.get())
        with patch.object(self.gui, 'execute') as execute:
            self.emit(widget, '<B1-Motion>', x, target_y + 15, 3080)
            self.emit(widget, '<ButtonRelease-1>', x, target_y, 3100)
            helper.double_release(SimpleNamespace(x=x, y=target_y))
            execute.assert_not_called()
        self.assertEqual(self.gui.profile_path.read_bytes(), before)
        self.assertIsNone(helper.scroll_job)
        self.assertFalse(helper.cancelled)

    def test_failed_save_busy_state_and_drop_outside_keep_original_order(self):
        before = self.gui.profile_path.read_bytes()
        with patch.object(self.gui, 'persist_profiles', side_effect=OSError('Test write failure')), \
             patch('app.messagebox.showerror') as error:
            self.drag(self.gui.ops, 0, 2)
            error.assert_called_once()
        self.assertIn('No se pudo cambiar', self.gui.reorder_hint.get())
        self.assertEqual(self.gui.profiles, self.original)
        self.assertEqual(self.gui.profile_path.read_bytes(), before)
        self.assertEqual(self.gui.ops.get(0), self.original['machines'][0]['operations'][0]['name'])
        self.gui.busy = True
        self.drag(self.gui.ops, 0, 2)
        self.gui.busy = False
        self.assertEqual(self.gui.profile_path.read_bytes(), before)
        x, y = self.point(self.gui.ops, 0)
        self.clock += 2000
        self.emit(self.gui.ops, '<ButtonPress-1>', x, y, self.clock)
        self.emit(self.gui.ops, '<B1-Motion>', -20, y + 40, self.clock + 50)
        self.assertEqual(str(self.gui.ops.cget('cursor')), 'no')
        self.assertIn('cancelar', self.gui.ops_reorder.ghost.cget('text'))
        self.emit(self.gui.ops, '<ButtonRelease-1>', -20, y + 40, self.clock + 100)
        self.assertIsNone(self.gui.ops_reorder.ghost)
        self.assertIn('cancelada', self.gui.reorder_hint.get())
        self.assertEqual(self.gui.profile_path.read_bytes(), before)

    def test_double_click_still_executes_and_drag_scrolls_to_hidden_rows(self):
        x, y = self.point(self.gui.ops, 0)
        with patch.object(self.gui, 'execute') as execute:
            for offset in (0, 100):
                self.emit(self.gui.ops, '<ButtonPress-1>', x, y, 4000 + offset)
                self.emit(self.gui.ops, '<ButtonRelease-1>', x, y, 4010 + offset)
            execute.assert_called_once()
        last_visible = self.gui.ops.nearest(self.gui.ops.winfo_height() - 2)
        self.assertLess(last_visible, self.gui.ops.size() - 1)
        self.emit(self.gui.ops, '<ButtonPress-1>', x, y, 7000)
        bottom = self.gui.ops.winfo_height() - 2
        self.emit(self.gui.ops, '<B1-Motion>', x, bottom, 7050)
        deadline = time.monotonic() + 0.7
        while time.monotonic() < deadline:
            self.gui.update()
            time.sleep(0.02)
        target = self.gui.ops.nearest(bottom)
        self.assertGreater(target, last_visible)
        self.emit(self.gui.ops, '<ButtonRelease-1>', x, bottom, 8000)
        self.assertEqual(self.gui.current()['operations'][target], self.original['machines'][0]['operations'][0])
        self.assertIsNone(self.gui.ops_reorder.scroll_job)

    def test_editor_order_is_draft_until_saved_and_survives_reopening(self):
        before = self.gui.profile_path.read_bytes()
        editor = self.gui.edit_profiles()
        self.gui.update()
        self.drag(editor.actions, 0, 2)
        self.assertIn('Pendiente de guardar', editor.reorder_hint.get())
        expected = copy.deepcopy(editor.machine()['operations'])
        self.assertNotEqual(expected, self.original['machines'][0]['operations'])
        self.assertEqual(self.gui.profile_path.read_bytes(), before)
        with patch('editor.messagebox.askyesno', return_value=True):
            editor.close()
        self.assertEqual(self.gui.profiles, self.original)
        editor = self.gui.edit_profiles()
        self.gui.update()
        self.drag(editor.actions, 0, 2)
        editor.save()
        self.assertEqual(self.gui.current()['operations'], expected)
        self.assertEqual(read_profile(self.gui.profile_path)['machines'][1], self.original['machines'][1])
        reopened = app.App(check_updates=False)
        try:
            reopened.withdraw()
            reopened.update()
            self.assertEqual(reopened.current()['operations'], expected)
            self.assertEqual(reopened.ops.get(0, 'end'), tuple(op['name'] for op in expected))
        finally:
            self.destroy_gui(reopened)


if __name__ == '__main__':
    unittest.main()
