"""Select machines or individual commands for portable profile files."""
import tkinter as tk
from tkinter import ttk, messagebox
from core import suggest_profile_destinations, resolve_profile_destinations
from ui_theme import UI


class ProfilePicker(tk.Toplevel):
    def __init__(self, parent, profiles, mode, local_profiles=None):
        super().__init__(parent)
        self.title('Seleccionar perfiles para ' + ('exportar' if mode == 'export' else 'importar'))
        self.geometry('780x680' if mode == 'import' else '640x580')
        self.minsize(*((640, 560) if mode == 'import' else (520, 420)))
        self.configure(bg=UI['canvas'])
        self.profiles = profiles
        self.mode = mode
        self.selection = {machine['name']: None for machine in profiles['machines']} if mode == 'export' else {}
        self.result = None
        self.rows = {}
        self.local_profiles = local_profiles or {'machines': []}
        self.local_names = [machine['name'] for machine in self.local_profiles['machines']]
        self.destinations = suggest_profile_destinations(self.local_profiles, profiles) if mode == 'import' else {}

        root = ttk.Frame(self, padding=16)
        root.pack(fill='both', expand=True)
        help_text = (
            'Marca un equipo para incluir su conexión y todas sus acciones. '
            'También puedes marcar solo las acciones que quieras compartir.'
            if mode == 'export' else
            'Elige el destino de cada equipo del archivo. Importar un equipo completo sustituye la conexión y todas '
            'las acciones del destino local. Marca acciones concretas para conservar la conexión y las demás acciones.'
        )
        ttk.Label(root, text=help_text, wraplength=590, justify='left').pack(anchor='w', pady=(0, 10))
        frame = ttk.Frame(root)
        frame.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(frame, show='tree headings' if mode == 'import' else 'tree', selectmode='browse',
                                 columns=('destination',) if mode == 'import' else ())
        self.tree.column('#0', width=390 if mode == 'import' else 520, anchor='w')
        if mode == 'import':
            self.tree.heading('#0', text='Equipo / acción del archivo')
            self.tree.heading('destination', text='Destino local')
            self.tree.column('destination', width=280, anchor='w')
        scrollbar = ttk.Scrollbar(frame, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)
        for machine_index, machine in enumerate(profiles['machines']):
            parent_id = f'm{machine_index}'
            self.tree.insert('', 'end', iid=parent_id, open=True)
            self.rows[parent_id] = (machine['name'], None)
            for operation_index, operation in enumerate(machine['operations']):
                child_id = f'{parent_id}o{operation_index}'
                self.tree.insert(parent_id, 'end', iid=child_id)
                self.rows[child_id] = (machine['name'], operation['name'])
        self.tree.bind('<ButtonRelease-1>', self.on_click)
        self.tree.bind('<space>', self.on_space)
        if mode == 'import':
            destination_frame = ttk.LabelFrame(root, text='Destino del equipo seleccionado', style='Card.TLabelframe', padding=12)
            destination_frame.pack(fill='x', pady=(10, 0))
            self.destination_label = ttk.Label(destination_frame, style='Card.TLabel', wraplength=570)
            self.destination_label.pack(anchor='w', pady=(0, 6))
            self.destination_selector = ttk.Combobox(destination_frame, state='readonly',
                values=['Crear equipo nuevo (nombre del archivo)'] + [f'Equipo local: {name}' for name in self.local_names])
            self.destination_selector.pack(fill='x')
            self.destination_selector.bind('<<ComboboxSelected>>', self.change_destination)
            ttk.Label(destination_frame, text='Cambiar el destino no marca acciones: usa las casillas de la lista.',
                      style='Card.TLabel', wraplength=570).pack(anchor='w', pady=(6, 0))
            self.tree.bind('<<TreeviewSelect>>', self.show_destination)
            self.tree.selection_set('m0')
            self.tree.focus('m0')
            self.show_destination()
        self.refresh()

        buttons = ttk.Frame(root)
        buttons.pack(fill='x', pady=(12, 0))
        ttk.Button(buttons, text='Marcar todo', command=self.select_all).pack(side='left')
        ttk.Button(buttons, text='Desmarcar todo', command=self.select_none).pack(side='left', padx=6)
        ttk.Button(buttons, text='Cancelar', command=self.destroy).pack(side='right')
        ttk.Button(buttons, text='Continuar', command=self.accept).pack(side='right', padx=6)
        self.transient(parent)
        self.grab_set()

    def refresh(self):
        for item_id, (name, operation) in self.rows.items():
            chosen = self.selection.get(name, set())
            if operation is None:
                if name in self.selection and chosen is None:
                    label = f'☑ {name} · equipo completo'
                elif chosen:
                    label = f'◩ {name} · {len(chosen)} acción(es)'
                else:
                    label = f'☐ {name}'
            else:
                mark = '☑' if chosen is None or operation in chosen else '☐'
                label = f'   {mark} {operation}'
            self.tree.item(item_id, text=label)
            if self.mode == 'import' and operation is None:
                target = self.destinations[name]
                self.tree.item(item_id, values=(target if target is not None else f'Nuevo: {name}',))

    def show_destination(self, event=None):
        selected = self.tree.selection()
        if not selected:
            return
        name, _ = self.rows[selected[0]]
        self.destination_label.configure(text=f'Equipo del archivo: {name}')
        target = self.destinations[name]
        self.destination_selector.current(0 if target is None else self.local_names.index(target) + 1)

    def change_destination(self, event=None):
        selected = self.tree.selection()
        if not selected:
            return
        name, _ = self.rows[selected[0]]
        index = self.destination_selector.current()
        self.destinations[name] = None if index == 0 else self.local_names[index - 1]
        self.refresh()

    def toggle(self, item_id):
        if item_id not in self.rows:
            return
        name, operation = self.rows[item_id]
        if operation is None:
            if self.selection.get(name, set()) is None:
                self.selection.pop(name, None)
            else:
                self.selection[name] = None
        else:
            if self.selection.get(name, set()) is None:
                machine = next(m for m in self.profiles['machines'] if m['name'] == name)
                chosen = {op['name'] for op in machine['operations']}
            else:
                chosen = set(self.selection.get(name, set()))
            if operation in chosen:
                chosen.remove(operation)
            else:
                chosen.add(operation)
            if chosen:
                self.selection[name] = chosen
            else:
                self.selection.pop(name, None)
        self.refresh()

    def on_click(self, event):
        if self.tree.identify_region(event.x, event.y) == 'tree':
            self.toggle(self.tree.identify_row(event.y))

    def on_space(self, event):
        self.toggle(self.tree.focus())
        return 'break'

    def select_all(self):
        self.selection = {machine['name']: None for machine in self.profiles['machines']}
        self.refresh()

    def select_none(self):
        self.selection = {}
        self.refresh()

    def accept(self):
        if not self.selection:
            messagebox.showinfo('Nada seleccionado', 'Marca al menos un equipo o una acción.', parent=self)
            return
        if self.mode == 'import':
            try:
                resolve_profile_destinations(self.local_profiles, self.profiles, self.selection, self.destinations)
            except ValueError as exc:
                messagebox.showerror('Destino inválido', str(exc), parent=self)
                return
        self.result = {name: None if selected is None else set(selected) for name, selected in self.selection.items()}
        self.destroy()
