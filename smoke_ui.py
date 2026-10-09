"""UI smoke test with an injected test transport and isolated profile storage."""
import json
import copy
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import app
from core import read_profile, Simulator


class TestTransport(Simulator):
    def reset_input_buffer(self):
        self.read()


with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
    app.DATA = Path(temp) / 'datos'
    gui = app.App()
    gui.withdraw()
    assert gui.handle_enter(SimpleNamespace(widget='.!combobox.popdown')) is None
    with patch.object(gui, 'send_from_input') as send:
        assert gui.handle_enter(SimpleNamespace(widget=gui.manual)) == 'break'
        send.assert_called_once()
    with patch.object(gui, 'execute') as execute:
        assert gui.handle_enter(SimpleNamespace(widget=gui.ops)) == 'break'
        execute.assert_called_once()
    def descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from descendants(child)
    original = copy.deepcopy(gui.profiles)
    shared = copy.deepcopy(original)
    shared['machines'][0]['name'] = '  vp1994+  '
    shared['machines'].append(dict(copy.deepcopy(shared['machines'][0]), name='Nombre distinto'))
    picker = app.ProfilePicker(gui, shared, 'import', local_profiles=original)
    assert picker.destinations['  vp1994+  '] == 'VP1994+'
    assert picker.destinations['Nombre distinto'] is None
    picker.tree.selection_set('m1o0')
    picker.show_destination()
    picker.destination_selector.current(1)
    picker.change_destination()
    assert picker.tree.item('m1', 'values') == ('VP1994+',)
    picker.toggle('m1o0')
    picker.accept()
    assert picker.result == {'Nombre distinto': {'Borrar Telecarga'}}
    assert picker.destinations['Nombre distinto'] == 'VP1994+'
    shared['machines'] = shared['machines'][:1]
    shared['machines'][0]['operations'][0]['steps'] = [{'send': 'X', 'delay_ms': 150}]
    import_path = Path(temp) / 'import.json'
    import_path.write_text(json.dumps(shared), encoding='utf-8')
    def choose_import(picker):
        picker.toggle('m0o0')
        picker.accept()
    with patch('app.filedialog.askopenfilename', return_value=str(import_path)), \
         patch.object(gui, 'wait_window', side_effect=choose_import), \
         patch('app.messagebox.askyesno', return_value=True) as confirmation:
        gui.import_profiles()
        confirmation.assert_called_once()
    imported = read_profile(gui.profile_path)
    assert [m['name'] for m in imported['machines']] == ['VP1994+']
    assert imported['machines'][0]['operations'][0]['steps'] == [{'send': 'X', 'delay_ms': 150}]
    assert imported['machines'][0]['connection'] == original['machines'][0]['connection']
    assert read_profile(gui.profile_path.with_name('machines.backup.json')) == original
    gui.store_profiles(original, 'VP1994+')
    gui.edit_appearance()
    dialog = next(child for child in gui.winfo_children() if isinstance(child, app.tk.Toplevel))
    widgets = list(descendants(dialog))
    next(widget for widget in widgets if isinstance(widget, app.ttk.Spinbox)).set('16')
    next(widget for widget in widgets if isinstance(widget, app.ttk.Button) and widget.cget('text') == 'Guardar').invoke()
    assert gui.appearance['size'] == 16
    assert gui.appearance_path.exists()
    assert gui.connection_fields['baudrate'].get() == '2400'
    gui.edit_connection()
    dialog = next(child for child in gui.winfo_children() if isinstance(child, app.tk.Toplevel))
    gui.connection_fields['baudrate'].set('4800')
    next(widget for widget in descendants(dialog) if isinstance(widget, app.ttk.Button) and widget.cget('text') == 'Cancelar').invoke()
    assert gui.connection_fields['baudrate'].get() == '2400'
    gui.edit_connection()
    dialog = next(child for child in gui.winfo_children() if isinstance(child, app.tk.Toplevel))
    gui.connection_fields['baudrate'].set('9600')
    gui.connection_fields['parity'].set('Par')
    gui.connection_fields['flow'].set('RTS/CTS')
    gui.connection_fields['enter'].set('CRLF')
    gui.port.set('COM7')
    next(widget for widget in descendants(dialog) if isinstance(widget, app.ttk.Button) and widget.cget('text') == 'Aplicar').invoke()
    assert '9600' in gui.connection_summary.cget('text')
    with patch('app.serial.Serial', return_value=TestTransport()) as serial_factory:
        gui.toggle_connection()
        serial_factory.assert_called_once_with('COM7', baudrate=9600, bytesize=8, parity='E', stopbits=1.0, timeout=0.1, write_timeout=1, xonxoff=False, rtscts=True, dsrdtr=False)
    assert str(gui.settings_btn.cget('state')) == 'disabled'
    assert gui.transport is not None
    assert not any(isinstance(widget, app.ttk.Checkbutton) and widget.cget('text') == 'Confirmar operaciones sensibles'
                   for widget in descendants(gui))
    for name in ('Borrar Telecarga', 'Borrar Estadísticas', 'Grabar Título', 'Machaque Título', 'Reset'):
        index = next(i for i, op in enumerate(gui.current()['operations']) if op['name'] == name)
        operation = gui.current()['operations'][index]
        # Previously exported profiles may still contain confirmation metadata.
        operation['confirm'] = 'Aviso antiguo que ya no debe mostrarse'
        gui.ops.selection_clear(0, 'end')
        gui.ops.selection_set(index)
        with patch('app.messagebox.askyesno') as confirmation, \
             patch.object(gui, 'ask_parameters', return_value={'Cantidad': '2'}) as parameters, \
             patch.object(gui, 'start_steps') as start:
            gui.execute()
            confirmation.assert_not_called()
            start.assert_called_once()
            if name == 'Machaque Título':
                parameters.assert_called_once()
                assert {'send': '2', 'delay_ms': 200} in start.call_args.args[1]
            else:
                parameters.assert_not_called()
        operation.pop('confirm')
    gui.ops.selection_clear(0, 'end')
    index = next(i for i, op in enumerate(gui.current()['operations']) if op['name'] == 'Versión telecarga')
    gui.ops.selection_set(index)
    gui.execute()
    deadline = time.monotonic() + 4
    while gui.busy and time.monotonic() < deadline:
        gui.update()
        time.sleep(0.01)
    assert not gui.busy
    assert any("TX b'T'" in line for line in gui.history)
    assert any('[SIM eco]' in line for line in gui.history)
    assert any("TX b'\\r\\n'" in line for line in gui.history)
    gui.disconnect()
    gui.geometry('900x600+120+120')
    gui.deiconify()
    gui.update()
    offsets = []
    def check_parameter_dialog():
        dialog = next(child for child in gui.winfo_children()
                      if isinstance(child, app.tk.Toplevel) and child.title() == 'Valores para Machaque Título')
        dialog.update_idletasks()
        offsets.append((dialog.winfo_rootx() - gui.winfo_rootx(),
                        dialog.winfo_rooty() - gui.winfo_rooty(),
                        dialog.winfo_width(), dialog.winfo_height()))
        dialog.destroy()
    gui.after(100, check_parameter_dialog)
    assert gui.ask_parameters('Machaque Título', [{'parameter': 'Cantidad', 'default': '50', 'kind': 'number'}]) is None
    assert offsets
    dx, dy, width, height = offsets[0]
    assert abs(dx - (gui.winfo_width() - width) // 2) <= 2
    assert abs(dy - (gui.winfo_height() - height) // 2) <= 2
    gui.withdraw()
    assert str(gui.settings_btn.cget('state')) == 'normal'
    gui.save_connection()
    saved = read_profile(gui.profile_path)['machines'][0]['connection']
    assert (saved['port'], saved['baudrate'], saved['parity'], saved['flow'], saved['enter']) == ('COM7', 9600, 'E', 'rtscts', '\r\n')
    gui.connection_fields['baudrate'].set('abc')
    with patch('app.messagebox.showerror') as error, patch('app.serial.Serial') as serial_factory:
        gui.toggle_connection()
        error.assert_called_once()
        serial_factory.assert_not_called()
    gui.change_machine()
    editor = gui.edit_profiles()
    assert editor is not None
    editor.new_machine()
    editor.fields['name'].set('Equipo prueba')
    recorder = editor.record_action()
    assert not hasattr(recorder, 'confirm')
    recorder.delay.set('350')
    recorder.toggle_recording()
    for keysym, char in [('Return', '\r'), ('O', 'O'), ('0', '0')]:
        recorder.capture_key(SimpleNamespace(keysym=keysym, char=char, state=0))
    recorder.toggle_recording()
    recorder.table.selection_set('1')
    recorder.step_delay.set('150')
    recorder.apply_selected()
    recorder.name.set('Leer switch de prueba')
    recorder.save()
    editor.save()
    assert gui.machine.get() == 'Equipo prueba'
    persisted = read_profile(gui.profile_path)
    assert len(persisted['machines'][0]['operations']) == len(original['machines'][0]['operations'])
    operation = persisted['machines'][1]['operations'][0]
    assert operation['name'] == 'Leer switch de prueba'
    assert [s['send'] for s in operation['steps']] == ['<ENTER>', 'O', '0']
    assert [s['delay_ms'] for s in operation['steps']] == [350, 150, 350]
    editor = gui.edit_profiles()
    editor.actions.selection_set(0)
    recorder = editor.record_action(0)
    assert recorder.steps == operation['steps']
    recorder.delay.set('250')
    recorder.apply_all()
    recorder.save()
    editor.save()
    assert [s['delay_ms'] for s in read_profile(gui.profile_path)['machines'][1]['operations'][0]['steps']] == [250, 250, 250]
    editor = gui.edit_profiles()
    with patch('editor.messagebox.askyesno', return_value=False):
        editor.delete_machine()
    assert len(editor.draft['machines']) == 2
    with patch('editor.messagebox.askyesno', return_value=True):
        editor.delete_machine()
    assert editor.machine()['name'] == 'VP1994+'
    assert editor.actions.size() == len(original['machines'][0]['operations'])
    assert len(read_profile(gui.profile_path)['machines']) == 2
    with patch('editor.messagebox.showinfo') as info, patch('editor.messagebox.askyesno') as confirmation:
        editor.delete_machine()
        info.assert_called_once()
        confirmation.assert_not_called()
    editor.save()
    assert gui.machine.get() == 'VP1994+'
    assert len(read_profile(gui.profile_path)['machines']) == 1
    gui.close_app()
    reopened = app.App()
    reopened.withdraw()
    assert reopened.appearance['size'] == 16
    assert [m['name'] for m in reopened.profiles['machines']] == ['VP1994+']
    reopened.close_app()
print('Interfaz: parámetros editables, conexión, validación, guardado, grabación y edición correctos.')
