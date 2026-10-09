"""Visual equipment editor and local keyboard action recorder."""
import copy
import tkinter as tk
from tkinter import ttk, messagebox

from core import validate, validate_parameter_step
from ui_theme import UI


def key_command(keysym, char, control=False):
    special = {'Return': '<ENTER>', 'KP_Enter': '<ENTER>', 'Tab': '\t',
               'Escape': '\x1b', 'BackSpace': '\b', 'Delete': '\x7f'}
    if keysym in special:
        return special[keysym]
    if control and len(keysym) == 1 and 'a' <= keysym.lower() <= 'z':
        return chr(ord(keysym.lower()) - ord('a') + 1)
    if len(char) == 1 and 32 <= ord(char) <= 126:
        return char
    return None


def delay_value(value):
    delay = int(value)
    if not 0 <= delay <= 60000:
        raise ValueError('El delay debe estar entre 0 y 60000 ms.')
    return delay


def show_key(value):
    names = {'<ENTER>': 'Intro', '\t': 'Tab', '\x1b': 'Esc', '\b': 'Retroceso', '\x7f': 'Supr', ' ': 'Espacio'}
    return names.get(value, value if value.isprintable() else repr(value))


def show_step(step):
    return show_key(step['send']) if 'send' in step else f"Valor variable: {step['parameter']} (inicial: {step['default']})"


class ActionRecorder(tk.Toplevel):
    def __init__(self, parent, operation, on_save):
        super().__init__(parent)
        self.title('Grabar comando' if operation is None else 'Editar acción')
        self.geometry('760x680')
        self.minsize(700, 680)
        self.configure(bg=UI['canvas'])
        self.on_save = on_save
        self.original = copy.deepcopy(operation or {})
        self.steps = copy.deepcopy(self.original.get('steps', []))
        self.recording = False
        root = ttk.Frame(self, padding=12)
        root.pack(fill='both', expand=True)
        intro = ttk.Frame(root, style='Card.TFrame', padding=(14, 10))
        intro.pack(fill='x', pady=(0, 8))
        ttk.Label(intro, text='Grabar acción', style='Section.TLabel').pack(anchor='w')
        ttk.Label(intro, text='Graba teclas, inserta valores variables y ajusta sus pausas. La grabación no envía comandos al equipo.',
                  style='Subtitle.TLabel', wraplength=670).pack(anchor='w', pady=(4, 0))
        bar = ttk.Frame(root)
        bar.pack(fill='x', pady=8)
        self.record_btn = ttk.Button(bar, text='Grabar', command=self.toggle_recording, style='Primary.TButton')
        self.record_btn.pack(side='left')
        ttk.Label(bar, text='Delay por tecla (ms)').pack(side='left', padx=(15, 6))
        self.delay = tk.StringVar(value='200')
        ttk.Spinbox(bar, from_=0, to=60000, increment=50, textvariable=self.delay, width=8).pack(side='left')
        ttk.Button(bar, text='Aplicar a todas', command=self.apply_all).pack(side='left', padx=8)
        self.capture = tk.Text(root, height=2, font=('Consolas', 12), bg='#152132', fg='#dce7f4',
                               insertbackground='white', takefocus=True, relief='flat', padx=8, pady=6)
        self.capture.pack(fill='x')
        self.capture.insert('1.0', 'Pulsa Grabar y escribe aquí. Intro, Tab, Esc y Retroceso se graban como comandos.')
        self.capture.bind('<KeyPress>', self.capture_key)
        self.capture.bind('<<Paste>>', lambda _: 'break')
        self.capture.bind('<<Cut>>', lambda _: 'break')
        self.capture.bind('<Button-2>', lambda _: 'break')
        self.state_label = ttk.Label(root, text='Grabación detenida', style='Status.TLabel')
        self.state_label.pack(anchor='w', pady=6)
        table_frame = ttk.Frame(root, style='Border.TFrame', padding=1)
        table_frame.pack(fill='both', expand=True)
        self.table = ttk.Treeview(table_frame, columns=('key', 'delay'), show='headings', height=4, selectmode='browse')
        self.table.heading('key', text='Tecla / comando')
        self.table.heading('delay', text='Pausa después de enviar (ms)')
        self.table.column('key', width=380)
        self.table.column('delay', width=220)
        table_scroll = ttk.Scrollbar(table_frame, command=self.table.yview)
        self.table.configure(yscrollcommand=table_scroll.set)
        table_scroll.pack(side='right', fill='y')
        self.table.pack(side='left', fill='both', expand=True)
        self.table.bind('<<TreeviewSelect>>', self.selected_step)
        row = ttk.Frame(root)
        row.pack(fill='x', pady=8)
        self.step_delay = tk.StringVar(value='200')
        ttk.Spinbox(row, from_=0, to=60000, increment=50, textvariable=self.step_delay, width=8).pack(side='left')
        ttk.Button(row, text='Cambiar pausa seleccionada', command=self.apply_selected).pack(side='left', padx=6)
        ttk.Button(row, text='Eliminar paso', command=self.remove_step).pack(side='left')
        ttk.Button(row, text='Vaciar', command=self.clear_steps).pack(side='right')
        variable_row = ttk.Frame(root)
        variable_row.pack(fill='x')
        ttk.Button(variable_row, text='Insertar valor variable', command=self.insert_parameter).pack(side='left')
        ttk.Button(variable_row, text='Editar valor seleccionado', command=self.edit_parameter).pack(side='left', padx=8)
        form = ttk.LabelFrame(root, text='Datos de la acción', style='Card.TLabelframe', padding=(12, 8))
        form.pack(fill='x', pady=(8, 4))
        self.name = tk.StringVar(value=self.original.get('name', ''))
        self.description = tk.StringVar(value=self.original.get('description', ''))
        for i, (label, variable) in enumerate((('Nombre de la acción', self.name), ('Descripción', self.description))):
            ttk.Label(form, text=label, style='Card.TLabel').grid(row=i, column=0, sticky='w', padx=(0, 8), pady=3)
            ttk.Entry(form, textvariable=variable).grid(row=i, column=1, sticky='ew')
        form.columnconfigure(1, weight=1)
        ttk.Button(root, text='Guardar acción', command=self.save, style='Primary.TButton').pack(anchor='e', pady=(8, 0))
        self.refresh()
        self.transient(parent)
        self.grab_set()
        self.protocol('WM_DELETE_WINDOW', self.close)

    def toggle_recording(self):
        if not self.recording:
            try:
                delay_value(self.delay.get())
            except ValueError as exc:
                messagebox.showerror('Delay inválido', str(exc), parent=self)
                return
        self.recording = not self.recording
        self.record_btn.configure(text='Detener grabación' if self.recording else 'Continuar grabación')
        self.state_label.configure(text='Grabando · haz clic en el recuadro para capturar teclas' if self.recording else 'Grabación detenida · asigna un nombre y guarda')
        if self.recording:
            self.capture.focus_set()

    def capture_key(self, event):
        if self.recording:
            value = key_command(event.keysym, event.char, bool(event.state & 0x4))
            if value is not None:
                try:
                    delay = delay_value(self.delay.get())
                except ValueError:
                    self.state_label.configure(text='Delay inválido: corrígelo antes de seguir grabando')
                    return 'break'
                self.steps.append({'send': value, 'delay_ms': delay})
                self.refresh()
            elif event.keysym not in ('Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Caps_Lock'):
                self.state_label.configure(text=f'Tecla no admitida: {event.keysym}. Usa caracteres ASCII o Intro/Tab/Esc/Retroceso/Supr.')
        return 'break'

    def refresh(self):
        self.table.delete(*self.table.get_children())
        for i, step in enumerate(self.steps):
            self.table.insert('', 'end', iid=str(i), values=(show_step(step), step.get('delay_ms', 0)))
        self.capture.delete('1.0', 'end')
        self.capture.insert('1.0', ' → '.join(show_step(s) for s in self.steps) or 'Pulsa Grabar y escribe aquí.')
        if self.steps:
            self.table.see(str(len(self.steps) - 1))
        self.capture.see('end')

    def selected_step(self, event=None):
        selection = self.table.selection()
        if selection:
            self.step_delay.set(str(self.steps[int(selection[0])].get('delay_ms', 0)))

    def parameter_dialog(self, original=None):
        dialog = tk.Toplevel(self)
        dialog.title('Valor variable')
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill='both', expand=True)
        name = tk.StringVar(value=(original or {}).get('parameter', ''))
        default = tk.StringVar(value=(original or {}).get('default', ''))
        kind = tk.StringVar(value='Número' if (original or {}).get('kind', 'number') == 'number' else 'Texto')
        name_entry = ttk.Entry(frame, textvariable=name, width=30)
        for row, (label, widget) in enumerate((
            ('Nombre que se pedirá al ejecutar', name_entry),
            ('Valor inicial', ttk.Entry(frame, textvariable=default, width=30)),
            ('Tipo', ttk.Combobox(frame, textvariable=kind, values=('Número', 'Texto'), state='readonly', width=27)),
        )):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=5)
            widget.grid(row=row, column=1, sticky='ew', pady=5)
        result = {'step': None}
        def accept(event=None):
            step = {'parameter': name.get().strip(), 'default': default.get(),
                    'kind': 'number' if kind.get() == 'Número' else 'text',
                    'delay_ms': original['delay_ms'] if original else delay_value(self.delay.get())}
            try:
                validate_parameter_step(step)
                if any(i != editing_index and other.get('parameter') == step['parameter'] and
                       (other['kind'], other['default']) != (step['kind'], step['default'])
                       for i, other in enumerate(self.steps)):
                    raise ValueError('Este nombre ya existe con otro tipo o valor inicial.')
            except ValueError as exc:
                messagebox.showerror('Valor variable inválido', str(exc), parent=dialog)
                return
            result['step'] = step
            dialog.destroy()
        editing_index = next((i for i, step in enumerate(self.steps) if step is original), -1)
        buttons = ttk.Frame(frame)
        buttons.grid(row=3, column=0, columnspan=2, sticky='e', pady=(12, 0))
        ttk.Button(buttons, text='Cancelar', command=dialog.destroy).pack(side='right')
        ttk.Button(buttons, text='Aceptar', command=accept).pack(side='right', padx=(0, 8))
        dialog.bind('<Return>', accept)
        dialog.bind('<Escape>', lambda _: dialog.destroy())
        dialog.transient(self)
        dialog.grab_set()
        name_entry.focus_set()
        dialog.wait_window()
        return result['step']

    def insert_parameter(self):
        try:
            delay_value(self.delay.get())
        except ValueError as exc:
            messagebox.showerror('Delay inválido', str(exc), parent=self)
            return
        step = self.parameter_dialog()
        if step is not None:
            selection = self.table.selection()
            index = int(selection[0]) + 1 if selection else len(self.steps)
            self.steps.insert(index, step)
            self.refresh()
            self.table.selection_set(str(index))
            if self.recording:
                self.capture.focus_set()

    def edit_parameter(self):
        selection = self.table.selection()
        if not selection:
            return
        index = int(selection[0])
        if 'parameter' not in self.steps[index]:
            messagebox.showinfo('Selecciona un valor variable', 'Selecciona un paso de valor variable para editarlo.', parent=self)
            return
        step = self.parameter_dialog(self.steps[index])
        if step is not None:
            self.steps[index] = step
            self.refresh()
            self.table.selection_set(str(index))

    def apply_selected(self):
        selection = self.table.selection()
        if not selection:
            return
        try:
            self.steps[int(selection[0])]['delay_ms'] = delay_value(self.step_delay.get())
            self.refresh()
            self.table.selection_set(selection[0])
        except ValueError as exc:
            messagebox.showerror('Delay inválido', str(exc), parent=self)

    def apply_all(self):
        try:
            delay = delay_value(self.delay.get())
            for step in self.steps:
                step['delay_ms'] = delay
            self.refresh()
        except ValueError as exc:
            messagebox.showerror('Delay inválido', str(exc), parent=self)

    def remove_step(self):
        selection = self.table.selection()
        if selection:
            del self.steps[int(selection[0])]
            self.refresh()

    def clear_steps(self):
        if self.steps and messagebox.askyesno('Vaciar grabación', '¿Eliminar todas las teclas de esta acción?', parent=self):
            self.steps.clear()
            self.refresh()

    def save(self):
        name = self.name.get().strip()
        if not name or not self.steps:
            messagebox.showerror('Acción incompleta', 'Graba al menos una tecla y asigna un nombre.', parent=self)
            return
        operation = dict(self.original, name=name, description=self.description.get().strip(), steps=copy.deepcopy(self.steps))
        operation.pop('confirm', None)
        try:
            self.on_save(operation)
        except ValueError as exc:
            messagebox.showerror('No se pudo guardar', str(exc), parent=self)
            return
        self.recording = False
        self.destroy()
        self.master.grab_set()

    def close(self):
        if messagebox.askyesno('Cerrar grabación', '¿Cerrar sin guardar esta acción?', parent=self):
            self.destroy()
            self.master.grab_set()


class ProfileEditor(tk.Toplevel):
    def __init__(self, parent, profiles, selected_name, on_save):
        super().__init__(parent)
        self.title('Equipos y acciones')
        self.geometry('900x700')
        self.minsize(820, 700)
        self.configure(bg=UI['canvas'])
        self.draft = copy.deepcopy(profiles)
        self.on_save = on_save
        self.index = next(i for i, m in enumerate(self.draft['machines']) if m['name'] == selected_name)
        root = ttk.Frame(self, padding=16)
        root.pack(fill='both', expand=True)
        header = ttk.Frame(root, style='Card.TFrame', padding=(14, 12))
        header.pack(fill='x')
        ttk.Label(header, text='Equipos y acciones', style='Section.TLabel').pack(anchor='w', pady=(0, 10))
        top = ttk.Frame(header, style='Card.TFrame')
        top.pack(fill='x')
        ttk.Label(top, text='Equipo', style='Card.TLabel').pack(side='left')
        self.selector = ttk.Combobox(top, state='readonly', width=30)
        self.selector.pack(side='left', padx=8)
        self.selector.bind('<<ComboboxSelected>>', self.choose_machine)
        ttk.Button(top, text='Crear nuevo equipo', command=self.new_machine).pack(side='left')
        ttk.Button(top, text='Eliminar equipo', command=self.delete_machine).pack(side='left', padx=(8, 0))
        form = ttk.LabelFrame(root, text='Configuración del equipo', style='Card.TLabelframe', padding=(14, 10))
        form.pack(fill='x', pady=10)
        fields = [('Nombre', 'name', None), ('Puerto', 'port', None), ('Baudios', 'baudrate', ('2400', '4800', '9600', '19200', '38400', '57600', '115200')),
                  ('Bits de datos', 'bytesize', ('5', '6', '7', '8')), ('Paridad', 'parity', ('Ninguna', 'Par', 'Impar', 'Marca', 'Espacio')),
                  ('Bits de parada', 'stopbits', ('1', '1.5', '2')), ('Control de flujo', 'flow', ('Ninguno', 'RTS/CTS', 'XON/XOFF', 'DSR/DTR')),
                  ('Intro', 'enter', ('CR', 'LF', 'CRLF'))]
        self.fields = {}
        for i, (label, key, values) in enumerate(fields):
            row, col = divmod(i, 2)
            variable = self.fields[key] = tk.StringVar()
            ttk.Label(form, text=label, style='Card.TLabel').grid(row=row * 2, column=col, sticky='w', padx=(0, 16), pady=(3, 0))
            widget = ttk.Combobox(form, textvariable=variable, values=values,
                                  state='normal' if key == 'baudrate' else 'readonly', width=30) if values else ttk.Entry(form, textvariable=variable, width=32)
            widget.grid(row=row * 2 + 1, column=col, sticky='ew', padx=(0, 16), pady=(0, 5))
            form.columnconfigure(col, weight=1)
        actions_card = ttk.Frame(root, style='Card.TFrame', padding=(14, 12))
        actions_card.pack(fill='both', expand=True)
        ttk.Label(actions_card, text='Acciones del equipo', style='Section.TLabel').pack(anchor='w')
        list_frame = ttk.Frame(actions_card, style='Border.TFrame', padding=1)
        list_frame.pack(fill='both', expand=True, pady=(8, 10))
        self.actions = tk.Listbox(list_frame, font=('Segoe UI', 10), exportselection=False, height=8, width=1,
                                  bg=UI['surface_alt'], fg=UI['text'], selectbackground=UI['accent'],
                                  selectforeground=UI['surface'], relief='flat', borderwidth=0, highlightthickness=0)
        actions_scroll = ttk.Scrollbar(list_frame, command=self.actions.yview)
        self.actions.configure(yscrollcommand=actions_scroll.set)
        actions_scroll.pack(side='right', fill='y')
        self.actions.pack(side='left', fill='both', expand=True)
        buttons = ttk.Frame(actions_card, style='Card.TFrame')
        buttons.pack(fill='x')
        ttk.Button(buttons, text='Grabar nuevo comando', command=self.record_action, style='Primary.TButton').pack(side='left')
        ttk.Button(buttons, text='Editar acción y pausas', command=self.edit_action).pack(side='left', padx=8)
        ttk.Button(buttons, text='Eliminar acción', command=self.delete_action).pack(side='left')
        footer = ttk.Frame(root)
        footer.pack(fill='x', pady=(10, 0))
        ttk.Label(footer, text='Los cambios se guardan al pulsar Guardar equipos y acciones.',
                  style='Status.TLabel', wraplength=480).pack(side='left')
        ttk.Button(footer, text='Guardar equipos y acciones', command=self.save,
                   style='Primary.TButton').pack(side='right')
        self.load_machine()
        self.transient(parent)
        self.grab_set()
        self.protocol('WM_DELETE_WINDOW', self.close)

    def machine(self):
        return self.draft['machines'][self.index]

    def load_machine(self):
        machine = self.machine()
        self.selector.configure(values=[m['name'] for m in self.draft['machines']])
        self.selector.current(self.index)
        self.fields['name'].set(machine['name'])
        for key, variable in self.fields.items():
            if key != 'name':
                value = machine['connection'].get(key, {'port': 'COM1', 'flow': 'none', 'enter': '\r'}.get(key, ''))
                if key == 'enter':
                    value = {'\r': 'CR', '\n': 'LF', '\r\n': 'CRLF'}[value]
                elif key == 'parity':
                    value = {'N': 'Ninguna', 'E': 'Par', 'O': 'Impar', 'M': 'Marca', 'S': 'Espacio'}[value]
                elif key == 'flow':
                    value = {'none': 'Ninguno', 'rtscts': 'RTS/CTS', 'xonxoff': 'XON/XOFF', 'dsrdtr': 'DSR/DTR'}[value]
                variable.set(str(value).removesuffix('.0'))
        self.refresh_actions()

    def update_machine(self):
        machine = copy.deepcopy(self.machine())
        values = {k: v.get().strip() for k, v in self.fields.items()}
        machine['name'] = values['name']
        machine['connection'].update(port=values['port'], baudrate=int(values['baudrate']), bytesize=int(values['bytesize']),
                                     parity={'Ninguna': 'N', 'Par': 'E', 'Impar': 'O', 'Marca': 'M', 'Espacio': 'S'}[values['parity']],
                                     stopbits=float(values['stopbits']),
                                     flow={'Ninguno': 'none', 'RTS/CTS': 'rtscts', 'XON/XOFF': 'xonxoff', 'DSR/DTR': 'dsrdtr'}[values['flow']],
                                     enter={'CR': '\r', 'LF': '\n', 'CRLF': '\r\n'}[values['enter']])
        candidate = copy.deepcopy(self.draft)
        candidate['machines'][self.index] = machine
        validate(candidate)
        self.draft = candidate

    def choose_machine(self, event=None):
        new_index = self.selector.current()
        try:
            self.update_machine()
        except (ValueError, KeyError) as exc:
            self.selector.current(self.index)
            messagebox.showerror('Configuración inválida', str(exc), parent=self)
            return
        self.index = new_index
        self.load_machine()

    def new_machine(self):
        try:
            self.update_machine()
        except (ValueError, KeyError) as exc:
            messagebox.showerror('Configuración inválida', str(exc), parent=self)
            return
        name, number = 'Nuevo equipo', 2
        names = {m['name'] for m in self.draft['machines']}
        while name in names:
            name = f'Nuevo equipo {number}'
            number += 1
        self.draft['machines'].append({'name': name, 'connection': {'port': 'COM1', 'baudrate': 2400, 'bytesize': 8, 'parity': 'N', 'stopbits': 1, 'flow': 'none', 'enter': '\r'}, 'operations': []})
        self.index = len(self.draft['machines']) - 1
        self.load_machine()

    def delete_machine(self):
        if len(self.draft['machines']) == 1:
            messagebox.showinfo('Último equipo', 'Debe quedar al menos un equipo. Crea otro antes de eliminar este.', parent=self)
            return
        machine = self.machine()
        if not messagebox.askyesno('Eliminar equipo',
                                  f'¿Eliminar el equipo «{machine["name"]}» y todas sus acciones?\n'
                                  'La eliminación se guardará al pulsar Guardar equipos y acciones.', parent=self):
            return
        del self.draft['machines'][self.index]
        self.index = min(self.index, len(self.draft['machines']) - 1)
        self.load_machine()

    def refresh_actions(self):
        self.actions.delete(0, 'end')
        for op in self.machine()['operations']:
            self.actions.insert('end', op['name'])

    def record_action(self, index=None):
        operations = self.machine()['operations']
        def save_action(operation):
            if any(op['name'] == operation['name'] for i, op in enumerate(operations) if i != index):
                raise ValueError('Ya existe una acción con ese nombre en este equipo.')
            if index is None:
                operations.append(operation)
            else:
                operations[index] = operation
            self.refresh_actions()
        return ActionRecorder(self, None if index is None else operations[index], save_action)

    def edit_action(self):
        selected = self.actions.curselection()
        if selected:
            self.record_action(selected[0])

    def delete_action(self):
        selected = self.actions.curselection()
        if selected and messagebox.askyesno('Eliminar acción', '¿Eliminar la acción seleccionada?', parent=self):
            del self.machine()['operations'][selected[0]]
            self.refresh_actions()

    def save(self):
        try:
            self.update_machine()
            self.on_save(self.draft, self.machine()['name'])
        except (ValueError, KeyError, OSError) as exc:
            messagebox.showerror('No se pudo guardar', str(exc), parent=self)
            return
        self.destroy()

    def close(self):
        if messagebox.askyesno('Cerrar editor', '¿Cerrar sin guardar los cambios del editor?', parent=self):
            self.destroy()
