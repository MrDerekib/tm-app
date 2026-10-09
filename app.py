import json
import copy
import os
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser, font as tkfont

import serial
from serial.tools import list_ports
from core import read_profile, validate, select_profiles, merge_selected_profiles, run_steps, manual_text_steps, TerminalText, parameters_for, resolve_steps, upgrade_legacy_machaque, upgrade_legacy_passwords
from editor import ProfileEditor
from profile_picker import ProfilePicker
from ui_theme import UI
from storage import migrate_user_data

BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
DATA_ROOT = Path(os.environ.get('LOCALAPPDATA', str(Path.home())))
DATA = DATA_ROOT / 'TM App'
# Compatibility with previous versions only; new data is stored under TM App.
LEGACY_DATA = DATA_ROOT / 'EquipoTools'

class App(tk.Tk):
    def __init__(self):
        if sys.platform == 'win32':
            # Give this source-run Tk app its own Windows taskbar identity,
            # separate from the Python interpreter that launches it.
            import ctypes
            shell32 = ctypes.windll.shell32
            shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.c_wchar_p]
            shell32.SetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
            shell32.SetCurrentProcessExplicitAppUserModelID('Indra.TMApp.TerminalMantenimiento')
        super().__init__()
        self.title('TM App · Terminal de Mantenimiento')
        icon_path = BASE / 'assets' / 'tm-device-icon-small.png'
        header_icon_path = BASE / 'assets' / 'tm-device-icon-header.png'
        try:
            source_icon = tk.PhotoImage(file=str(icon_path))
            self.icon_large = source_icon
            self.icon_small = tk.PhotoImage(file=str(header_icon_path))
            self.icon_header = self.icon_small
            self.iconphoto(True, self.icon_large, self.icon_small)
        except tk.TclError:
            # The application remains usable when the optional artwork is absent.
            self.icon_large = None
            self.icon_small = None
            self.icon_header = None
        if sys.platform == 'win32':
            try:
                windows_icon = str(BASE / 'assets' / 'tm-app.ico')
                self.iconbitmap(default=windows_icon)
                self.iconbitmap(windows_icon)
            except tk.TclError:
                pass
        self.geometry('1120x740')
        self.minsize(900, 600)
        self.transport = None
        self.active_connection = None
        self.busy = False
        self.active_task_kind = None
        self.manual_queue = []
        self.cancel = threading.Event()
        self.reader_stop = threading.Event()
        self.events = queue.Queue()
        self.history = []
        self.terminal_text = TerminalText()
        self.session = 0
        migrate_user_data(DATA, LEGACY_DATA)
        self.preferences_path = DATA / 'preferences.json'
        confirm_operations = True
        try:
            preferences = json.loads(self.preferences_path.read_text(encoding='utf-8'))
            if isinstance(preferences, dict) and isinstance(preferences.get('confirm_operations'), bool):
                confirm_operations = preferences['confirm_operations']
        except (OSError, ValueError):
            pass
        self.confirm_operations = tk.BooleanVar(value=confirm_operations)
        self.appearance_path = DATA / 'appearance.json'
        self.appearance = {'family': 'Consolas', 'size': 10, 'foreground': '#dce7f4', 'background': '#152132'}
        try:
            saved = json.loads(self.appearance_path.read_text(encoding='utf-8'))
            if isinstance(saved, dict):
                family = saved.get('family', 'Consolas')
                if isinstance(family, str) and family in tkfont.families(self):
                    self.appearance['family'] = family
                size = saved.get('size', 10)
                if isinstance(size, int) and not isinstance(size, bool) and 6 <= size <= 48:
                    self.appearance['size'] = size
                for key in ('foreground', 'background'):
                    color = saved.get(key)
                    if isinstance(color, str):
                        try:
                            self.winfo_rgb(color)
                            self.appearance[key] = color
                        except tk.TclError:
                            pass
        except (OSError, ValueError):
            pass
        self.profile_path = DATA / 'machines.json'
        if not self.profile_path.exists():
            self.profile_path.write_bytes((BASE / 'machines.json').read_bytes())
        try:
            self.profiles = read_profile(self.profile_path)
        except Exception as exc:
            messagebox.showerror('Perfil inválido', f'{exc}\nSe cargará el perfil incluido sin sobrescribir el tuyo.')
            self.profiles = read_profile(BASE / 'machines.json')
        else:
            updated = upgrade_legacy_machaque(self.profiles)
            updated = upgrade_legacy_passwords(self.profiles) or updated
            if updated:
                try:
                    temporary = self.profile_path.with_suffix('.tmp')
                    temporary.write_text(json.dumps(self.profiles, ensure_ascii=False, indent=2), encoding='utf-8')
                    temporary.replace(self.profile_path)
                except OSError as exc:
                    messagebox.showwarning('Perfil no actualizado', f'El valor variable funcionará en esta sesión, pero no se pudo guardar: {exc}')
        self.build()
        self.machine.set(self.profiles['machines'][0]['name'])
        self.change_machine()
        self.refresh_ports()
        self.bind_all('<Return>', self.handle_enter, add='+')
        self.bind_all('<KP_Enter>', self.handle_enter, add='+')
        self.protocol('WM_DELETE_WINDOW', self.close_app)
        self.after(60, self.poll)

    def setup_styles(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TFrame', background=UI['canvas'])
        style.configure('Card.TFrame', background=UI['surface'])
        style.configure('Accent.TFrame', background=UI['accent'])
        style.configure('TLabel', background=UI['canvas'], foreground=UI['text'], font=('Segoe UI', 9))
        style.configure('Card.TLabel', background=UI['surface'], foreground=UI['text'])
        style.configure('Title.TLabel', background=UI['surface'], foreground=UI['text'], font=('Segoe UI', 19, 'bold'))
        style.configure('Subtitle.TLabel', background=UI['surface'], foreground=UI['muted'], font=('Segoe UI', 9))
        style.configure('Section.TLabel', background=UI['surface'], foreground=UI['text'], font=('Segoe UI', 11, 'bold'))
        style.configure('Status.TLabel', background=UI['canvas'], foreground=UI['muted'], font=('Segoe UI', 9))
        style.configure('Card.TLabelframe', background=UI['surface'], bordercolor=UI['border'], relief='solid')
        style.configure('Card.TLabelframe.Label', background=UI['surface'], foreground=UI['text'], font=('Segoe UI', 9, 'bold'))
        style.configure('TButton', background=UI['surface'], foreground=UI['text'], bordercolor=UI['border'],
                        lightcolor=UI['surface'], darkcolor=UI['border'], padding=(10, 6), font=('Segoe UI', 9))
        style.map('TButton', background=[('disabled', UI['disabled']), ('pressed', UI['accent_soft']), ('active', UI['accent_soft'])],
                  foreground=[('disabled', UI['muted'])])
        style.configure('Primary.TButton', background=UI['accent'], foreground=UI['surface'], bordercolor=UI['accent'],
                        lightcolor=UI['accent'], darkcolor=UI['accent'], padding=(12, 7), font=('Segoe UI', 9, 'bold'))
        style.map('Primary.TButton', background=[('disabled', UI['disabled']), ('pressed', UI['accent_hover']), ('active', UI['accent_hover'])],
                  foreground=[('disabled', UI['muted']), ('!disabled', UI['surface'])])
        style.configure('TCombobox', fieldbackground=UI['surface'], background=UI['surface'], foreground=UI['text'],
                        arrowcolor=UI['text'], bordercolor=UI['border'], lightcolor=UI['border'], darkcolor=UI['border'],
                        padding=4, font=('Segoe UI', 9))
        style.map('TCombobox', fieldbackground=[('disabled', UI['disabled']), ('readonly', UI['surface']), ('!disabled', UI['surface'])],
                  background=[('disabled', UI['disabled']), ('readonly', UI['surface']), ('!disabled', UI['surface'])],
                  foreground=[('disabled', UI['muted']), ('!disabled', UI['text'])],
                  selectbackground=[('readonly', UI['surface'])], selectforeground=[('readonly', UI['text'])],
                  arrowcolor=[('disabled', UI['muted']), ('!disabled', UI['text'])])
        style.configure('TEntry', fieldbackground=UI['surface'], foreground=UI['text'], bordercolor=UI['border'], padding=5)
        style.configure('TSpinbox', fieldbackground=UI['surface'], background=UI['surface'], foreground=UI['text'],
                        arrowcolor=UI['muted'], bordercolor=UI['border'], lightcolor=UI['border'],
                        darkcolor=UI['border'], padding=4)
        style.map('TSpinbox', fieldbackground=[('disabled', UI['disabled']), ('!disabled', UI['surface'])],
                  arrowcolor=[('disabled', UI['muted']), ('active', UI['accent']), ('!disabled', UI['muted'])])
        style.configure('Vertical.TScrollbar', background=UI['border'], troughcolor=UI['surface_alt'],
                        arrowcolor=UI['muted'], bordercolor=UI['surface_alt'], lightcolor=UI['border'],
                        darkcolor=UI['border'], gripcount=0, width=12)
        style.map('Vertical.TScrollbar', background=[('pressed', UI['accent_hover']), ('active', UI['accent'])],
                  arrowcolor=[('pressed', UI['surface']), ('active', UI['surface'])])
        style.configure('Card.TCheckbutton', background=UI['surface'], foreground=UI['text'], font=('Segoe UI', 9))
        style.map('Card.TCheckbutton', background=[('active', UI['surface'])])
        style.configure('Border.TFrame', background=UI['border'])
        style.configure('Treeview', background=UI['surface_alt'], fieldbackground=UI['surface_alt'],
                        foreground=UI['text'], bordercolor=UI['border'], rowheight=25, font=('Segoe UI', 9))
        style.map('Treeview', background=[('selected', UI['accent'])], foreground=[('selected', UI['surface'])])
        style.configure('Treeview.Heading', background=UI['accent_soft'], foreground=UI['text'],
                        bordercolor=UI['border'], font=('Segoe UI', 9, 'bold'))
        style.configure('TPanedwindow', background=UI['canvas'])

    def build(self):
        self.configure(bg=UI['canvas'])
        self.setup_styles()
        root = ttk.Frame(self, padding=(16, 14))
        root.pack(fill='both', expand=True)
        header = ttk.Frame(root, style='Card.TFrame', padding=(14, 10))
        header.pack(fill='x', pady=(0, 10))
        if self.icon_header is not None:
            ttk.Label(header, image=self.icon_header, style='Card.TLabel').pack(side='left', padx=(0, 12))
        else:
            ttk.Frame(header, style='Accent.TFrame', width=4).pack(side='left', fill='y', padx=(0, 12))
        title = ttk.Frame(header, style='Card.TFrame')
        title.pack(side='left')
        ttk.Label(title, text='TM App', style='Title.TLabel').pack(anchor='w')
        ttk.Label(title, text='Terminal de Mantenimiento  ·  RS-232', style='Subtitle.TLabel').pack(anchor='w')
        connection_card = ttk.Frame(root, style='Card.TFrame', padding=(14, 10))
        connection_card.pack(fill='x', pady=(0, 10))
        bar = ttk.Frame(connection_card, style='Card.TFrame')
        bar.pack(fill='x')
        ttk.Label(bar, text='Máquina', style='Card.TLabel').pack(side='left')
        self.machine = ttk.Combobox(bar, state='readonly', width=22, values=[m['name'] for m in self.profiles['machines']])
        self.machine.pack(side='left', padx=8)
        self.machine.bind('<<ComboboxSelected>>', self.change_machine)
        ttk.Label(bar, text='Puerto', style='Card.TLabel').pack(side='left', padx=(8, 0))
        self.port = ttk.Combobox(bar, width=12)
        self.port.pack(side='left', padx=8)
        self.refresh_btn = ttk.Button(bar, text='Actualizar', command=self.refresh_ports)
        self.refresh_btn.pack(side='left')
        self.connect_btn = ttk.Button(bar, text='Conectar', command=self.toggle_connection, style='Primary.TButton')
        self.connect_btn.pack(side='right')
        self.settings_btn = ttk.Button(bar, text='Configurar conexión', command=self.edit_connection)
        self.settings_btn.pack(side='right', padx=(0, 8))
        self.connection_fields = {key: tk.StringVar() for key in ('baudrate', 'bytesize', 'parity', 'stopbits', 'flow', 'enter')}
        self.connection_summary = ttk.Label(connection_card, style='Subtitle.TLabel')
        self.connection_summary.pack(anchor='w', pady=(8, 0))
        tools = ttk.Frame(root)
        tools.pack(fill='x', pady=(0, 12))
        self.edit_btn = ttk.Button(tools, text='Equipos y acciones', command=self.edit_profiles)
        self.edit_btn.pack(side='left')
        self.import_btn = ttk.Button(tools, text='Importar perfiles', command=self.import_profiles)
        self.import_btn.pack(side='left', padx=(8, 0))
        ttk.Button(tools, text='Exportar perfiles', command=self.export_profiles).pack(side='left', padx=8)
        ttk.Button(tools, text='Aspecto de la consola', command=self.edit_appearance).pack(side='left', padx=8)
        ttk.Button(tools, text='Guardar registro', command=self.save_log).pack(side='left', padx=8)
        self.stop_btn = ttk.Button(tools, text='Cancelar secuencia', command=self.stop, state='disabled')
        self.stop_btn.pack(side='right')
        body = ttk.Panedwindow(root, orient='horizontal')
        body.pack(fill='both', expand=True)
        left = ttk.Frame(body, padding=12, style='Card.TFrame')
        right = ttk.Frame(body, padding=12, style='Card.TFrame')
        body.add(left, weight=1)
        body.add(right, weight=3)
        ttk.Label(left, text='Operaciones', style='Section.TLabel').pack(anchor='w')
        operations_frame = ttk.Frame(left, style='Border.TFrame', padding=1)
        operations_frame.pack(fill='both', expand=True, pady=8)
        self.ops = tk.Listbox(operations_frame, font=('Segoe UI', 10), activestyle='none', exportselection=False,
                              bg=UI['surface_alt'], fg=UI['text'], selectbackground=UI['accent'],
                              selectforeground=UI['surface'], relief='flat', borderwidth=0,
                              highlightthickness=0, height=8)
        operations_scroll = ttk.Scrollbar(operations_frame, command=self.ops.yview)
        self.ops.configure(yscrollcommand=operations_scroll.set)
        operations_scroll.pack(side='right', fill='y')
        self.ops.pack(side='left', fill='both', expand=True)
        self.ops.bind('<<ListboxSelect>>', self.preview)
        self.ops.bind('<Double-Button-1>', self.execute_from_list)
        detail_frame = ttk.LabelFrame(left, text='Detalles de la operación', style='Card.TLabelframe', padding=6)
        detail_frame.pack(fill='x', pady=(0, 8))
        self.detail = tk.Text(detail_frame, width=1, height=4, wrap='word', font=('Segoe UI', 9), state='disabled',
                              bg=UI['surface_alt'], fg=UI['muted'], relief='flat', borderwidth=0, padx=6, pady=5)
        detail_scroll = ttk.Scrollbar(detail_frame, command=self.detail.yview)
        self.detail.configure(yscrollcommand=detail_scroll.set)
        detail_scroll.pack(side='right', fill='y')
        self.detail.pack(side='left', fill='x', expand=True)
        self.run_btn = ttk.Button(left, text='Ejecutar operación', command=self.execute,
                                  state='disabled', style='Primary.TButton')
        self.run_btn.pack(fill='x')
        ttk.Checkbutton(left, text='Confirmar operaciones sensibles', variable=self.confirm_operations,
                        command=self.save_preferences, style='Card.TCheckbutton').pack(anchor='w', pady=(8, 0))
        ttk.Label(right, text='Respuesta del equipo', style='Section.TLabel').pack(anchor='w')
        frame = ttk.Frame(right, style='Border.TFrame', padding=1)
        frame.pack(fill='both', expand=True, pady=8)
        self.console = tk.Text(frame, width=1, height=8, bg='#152132', fg='#dce7f4', insertbackground='white',
                               font=('Consolas', 10), wrap='word', state='disabled', relief='flat', borderwidth=0, padx=8, pady=7)
        scroll = ttk.Scrollbar(frame, command=self.console.yview)
        self.console.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.console.pack(fill='both', expand=True)
        self.apply_appearance(self.appearance)
        ttk.Label(right, text='Registro de envíos y conexión', style='Card.TLabel').pack(anchor='w')
        activity_frame = ttk.Frame(right, style='Border.TFrame', padding=1)
        activity_frame.pack(fill='x', pady=(4, 8))
        self.activity = tk.Text(activity_frame, width=1, height=3, font=('Consolas', 9), wrap='word', state='disabled',
                                bg=UI['surface_alt'], fg=UI['text'], relief='flat', borderwidth=0, padx=6, pady=5)
        activity_scroll = ttk.Scrollbar(activity_frame, command=self.activity.yview)
        self.activity.configure(yscrollcommand=activity_scroll.set)
        activity_scroll.pack(side='right', fill='y')
        self.activity.pack(fill='x')
        manual = ttk.Frame(right, style='Card.TFrame')
        manual.pack(fill='x')
        self.manual = ttk.Entry(manual)
        self.manual.pack(side='left', fill='x', expand=True)
        self.add_enter = tk.BooleanVar(value=False)
        ttk.Checkbutton(manual, text='Añadir Enter', variable=self.add_enter, style='Card.TCheckbutton').pack(side='left', padx=5)
        self.send_btn = ttk.Button(manual, text='Enviar', command=self.send_from_input,
                                   state='disabled', style='Primary.TButton')
        self.send_btn.pack(side='right')
        self.status = ttk.Label(root, text='Desconectado', style='Status.TLabel')
        self.status.pack(anchor='w', pady=(9, 0))

    def apply_appearance(self, values):
        self.console.configure(font=(values['family'], values['size']), fg=values['foreground'], bg=values['background'], insertbackground=values['foreground'])

    def save_preferences(self):
        try:
            temporary = self.preferences_path.with_suffix('.tmp')
            temporary.write_text(json.dumps({'confirm_operations': self.confirm_operations.get()}, indent=2), encoding='utf-8')
            temporary.replace(self.preferences_path)
        except OSError as exc:
            messagebox.showerror('No se pudieron guardar las preferencias', str(exc), parent=self)

    def edit_appearance(self):
        win = tk.Toplevel(self)
        win.title('Aspecto de la consola')
        win.resizable(False, False)
        root = ttk.Frame(win, padding=18)
        root.pack(fill='both', expand=True)
        family = tk.StringVar(value=self.appearance['family'])
        size = tk.StringVar(value=str(self.appearance['size']))
        colors = {key: self.appearance[key] for key in ('foreground', 'background')}
        ttk.Label(root, text='Tipografía').grid(row=0, column=0, sticky='w', pady=6)
        families = sorted(set(tkfont.families(self)), key=str.casefold)
        ttk.Combobox(root, textvariable=family, values=families, state='readonly', width=32).grid(row=0, column=1)
        ttk.Label(root, text='Tamaño (pt)').grid(row=1, column=0, sticky='w', pady=6)
        ttk.Spinbox(root, from_=6, to=48, textvariable=size, width=8).grid(row=1, column=1, sticky='w')
        preview_frame = ttk.Frame(root, width=440, height=180)
        preview_frame.grid(row=4, column=0, columnspan=2, pady=12, sticky='ew')
        preview_frame.pack_propagate(False)
        preview = tk.Text(preview_frame, width=1, height=1, wrap='word', state='disabled')
        preview_scroll = ttk.Scrollbar(preview_frame, command=preview.yview)
        preview.configure(yscrollcommand=preview_scroll.set)
        preview_scroll.pack(side='right', fill='y')
        preview.pack(fill='both', expand=True)
        preview.configure(state='normal')
        preview.insert('1.0', '> O:Input/Output\nOpcion: 0\n0:Switch Addr\n00000100')
        preview.configure(state='disabled')

        def values():
            points = int(size.get())
            if not 6 <= points <= 48:
                raise ValueError('El tamaño debe estar entre 6 y 48 puntos.')
            return dict(family=family.get(), size=points, **colors)

        def update_preview(*_):
            try:
                appearance = values()
                preview.configure(font=(appearance['family'], appearance['size']), fg=appearance['foreground'], bg=appearance['background'])
            except (ValueError, tk.TclError):
                pass

        def choose_color(key):
            chosen = colorchooser.askcolor(color=colors[key], parent=win, title='Color del texto' if key == 'foreground' else 'Color del fondo')[1]
            if chosen:
                colors[key] = chosen
                update_preview()

        ttk.Button(root, text='Color del texto…', command=lambda: choose_color('foreground')).grid(row=2, column=0, columnspan=2, sticky='ew', pady=4)
        ttk.Button(root, text='Color del fondo…', command=lambda: choose_color('background')).grid(row=3, column=0, columnspan=2, sticky='ew', pady=4)
        family.trace_add('write', update_preview)
        size.trace_add('write', update_preview)
        update_preview()

        def save():
            try:
                appearance = values()
                temp = self.appearance_path.with_suffix('.tmp')
                temp.write_text(json.dumps(appearance, ensure_ascii=False, indent=2), encoding='utf-8')
                temp.replace(self.appearance_path)
                self.appearance = appearance
                self.apply_appearance(appearance)
                win.destroy()
            except (ValueError, OSError, tk.TclError) as exc:
                messagebox.showerror('No se pudo guardar el aspecto', str(exc), parent=win)

        buttons = ttk.Frame(root)
        buttons.grid(row=5, column=0, columnspan=2, sticky='e')
        ttk.Button(buttons, text='Cancelar', command=win.destroy).pack(side='left', padx=6)
        ttk.Button(buttons, text='Guardar', command=save).pack(side='left')
        win.transient(self)
        win.grab_set()

    def current(self):
        return next(m for m in self.profiles['machines'] if m['name'] == self.machine.get())

    def change_machine(self, event=None):
        m = self.current()
        c = m['connection']
        self.port.set(c.get('port', 'COM1'))
        labels = {
            'parity': {'N': 'Ninguna', 'E': 'Par', 'O': 'Impar', 'M': 'Marca', 'S': 'Espacio'},
            'flow': {'none': 'Ninguno', 'rtscts': 'RTS/CTS', 'xonxoff': 'XON/XOFF', 'dsrdtr': 'DSR/DTR'},
            'enter': {'\r': 'CR', '\n': 'LF', '\r\n': 'CRLF'},
        }
        for key, variable in self.connection_fields.items():
            value = c.get(key, {'flow': 'none', 'enter': '\r'}.get(key))
            variable.set(labels[key][value] if key in labels else str(value).removesuffix('.0'))
        self.refresh_connection_summary()
        self.ops.delete(0, 'end')
        for op in m['operations']:
            self.ops.insert('end', op['name'])
        self.preview()

    def refresh_ports(self):
        self.port.configure(values=[p.device for p in list_ports.comports()])

    def read_connection(self):
        values = {key: variable.get().strip() for key, variable in self.connection_fields.items()}
        connection = dict(self.current()['connection'])
        connection.update(port=self.port.get().strip(), baudrate=int(values['baudrate']), bytesize=int(values['bytesize']),
                          parity={'Ninguna': 'N', 'Par': 'E', 'Impar': 'O', 'Marca': 'M', 'Espacio': 'S'}[values['parity']],
                          stopbits=float(values['stopbits']),
                          flow={'Ninguno': 'none', 'RTS/CTS': 'rtscts', 'XON/XOFF': 'xonxoff', 'DSR/DTR': 'dsrdtr'}[values['flow']],
                          enter={'CR': '\r', 'LF': '\n', 'CRLF': '\r\n'}[values['enter']])
        if not connection['port']:
            raise ValueError('Selecciona o escribe un puerto COM.')
        validate({'machines': [dict(self.current(), connection=connection)]})
        return connection

    def refresh_connection_summary(self):
        fields = {key: value.get() for key, value in self.connection_fields.items()}
        parity = {'Ninguna': 'N', 'Par': 'E', 'Impar': 'O', 'Marca': 'M', 'Espacio': 'S'}.get(fields['parity'], '?')
        flow = fields['flow'].lower()
        self.connection_summary.configure(text=f"{fields['baudrate']} baudios  ·  {fields['bytesize']}{parity}{fields['stopbits']}  ·  Flujo: {flow}  ·  Intro: {fields['enter']}")

    def edit_connection(self):
        if self.transport is not None:
            return
        previous = {key: variable.get() for key, variable in self.connection_fields.items()}
        dialog = tk.Toplevel(self)
        dialog.title('Configurar conexión RS-232')
        dialog.configure(bg=UI['canvas'])
        dialog.resizable(False, False)
        root = ttk.Frame(dialog, padding=16)
        root.pack(fill='both', expand=True)
        ttk.Label(root, text='Parámetros de conexión', font=('Segoe UI', 13, 'bold')).pack(anchor='w', pady=(0, 10))
        settings = ttk.LabelFrame(root, text='Puerto serie', style='Card.TLabelframe', padding=12)
        settings.pack(fill='x')
        fields = [('Baudios', 'baudrate', ('2400', '4800', '9600', '19200', '38400', '57600', '115200')),
                  ('Bits de datos', 'bytesize', ('5', '6', '7', '8')),
                  ('Paridad', 'parity', ('Ninguna', 'Par', 'Impar', 'Marca', 'Espacio')),
                  ('Bits de parada', 'stopbits', ('1', '1.5', '2')),
                  ('Control de flujo', 'flow', ('Ninguno', 'RTS/CTS', 'XON/XOFF', 'DSR/DTR')),
                  ('Intro', 'enter', ('CR', 'LF', 'CRLF'))]
        for index, (label, key, values) in enumerate(fields):
            row, column = divmod(index, 2)
            ttk.Label(settings, text=label, style='Card.TLabel').grid(row=row * 2, column=column, sticky='w', padx=(0, 14), pady=(5, 0))
            widget = ttk.Combobox(settings, textvariable=self.connection_fields[key], values=values,
                                  state='normal' if key == 'baudrate' else 'readonly', width=25)
            widget.grid(row=row * 2 + 1, column=column, sticky='ew', padx=(0, 14), pady=(0, 7))
            settings.columnconfigure(column, weight=1)
        ttk.Label(root, text='Aplicar usa estos valores al conectar. Guardar los conserva para este equipo.',
                  wraplength=540).pack(anchor='w', pady=(12, 8))
        buttons = ttk.Frame(root)
        buttons.pack(fill='x')
        def cancel():
            for key, value in previous.items():
                self.connection_fields[key].set(value)
            dialog.destroy()
        def apply(save=False):
            try:
                self.read_connection()
                if save and not self.save_connection(parent=dialog):
                    return
            except (ValueError, KeyError) as exc:
                messagebox.showerror('Conexión inválida', str(exc), parent=dialog)
                return
            self.refresh_connection_summary()
            dialog.destroy()
        ttk.Button(buttons, text='Cancelar', command=cancel).pack(side='right')
        ttk.Button(buttons, text='Guardar para este equipo', command=lambda: apply(True)).pack(side='right', padx=8)
        ttk.Button(buttons, text='Aplicar', command=apply, style='Primary.TButton').pack(side='right')
        dialog.transient(self)
        dialog.grab_set()
        dialog.protocol('WM_DELETE_WINDOW', cancel)

    def save_connection(self, parent=None):
        if self.transport is not None:
            return False
        try:
            data = copy.deepcopy(self.profiles)
            index = next(i for i, machine in enumerate(data['machines']) if machine['name'] == self.machine.get())
            data['machines'][index]['connection'] = self.read_connection()
            self.store_profiles(data, self.machine.get())
            return True
        except (ValueError, KeyError, OSError) as exc:
            messagebox.showerror('No se pudo guardar la conexión', str(exc), parent=parent or self)
            return False

    def preview(self, event=None):
        selected = self.ops.curselection()
        if selected:
            op = self.current()['operations'][selected[0]]
            steps = ' → '.join(s['send'] if 'send' in s else f"[{s['parameter']}: {s['default']}]" for s in op['steps'])
            description = op.get('description', '')
            text = f"{description}\nSecuencia: {steps}" if description else f'Secuencia: {steps}'
        else:
            text = 'Selecciona una operación'
        self.detail.configure(state='normal')
        self.detail.delete('1.0', 'end')
        self.detail.insert('1.0', text)
        self.detail.configure(state='disabled')

    def log(self, kind, text):
        # Escaped RX preserves exact received data in the exported diagnostic log.
        recorded = repr(text) if kind == 'RX' else text
        label = 'ENVÍO' if kind == 'DONE' else kind
        line = f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {label} {recorded}\n"
        self.history.append(line)
        target = self.console if kind == 'RX' else self.activity
        display = self.terminal_text.feed(text) if kind == 'RX' else line
        target.configure(state='normal')
        if kind == 'RX':
            target.delete('1.0', 'end')
        target.insert('end', display)
        target.see('end')
        target.configure(state='disabled')

    def controls(self):
        connected = self.transport is not None
        self.run_btn.configure(state='normal' if connected and not self.busy else 'disabled')
        # Manual commands and Enter stay available while an operation is active,
        # so the operator can interrupt it and type the next command immediately.
        self.send_btn.configure(state='normal' if connected else 'disabled')
        self.stop_btn.configure(state='normal' if self.busy else 'disabled')
        for widget in (self.edit_btn, self.import_btn, self.refresh_btn, self.settings_btn):
            widget.configure(state='disabled' if connected else 'normal')
        self.machine.configure(state='disabled' if connected else 'readonly')
        self.port.configure(state='disabled' if connected else 'normal')

    def toggle_connection(self):
        if self.transport is not None:
            self.disconnect()
            return
        try:
            c = self.read_connection()
            flow = c.get('flow', 'none')
            transport = serial.Serial(c['port'], baudrate=c['baudrate'], bytesize=c['bytesize'], parity=c['parity'], stopbits=c['stopbits'], timeout=0.1, write_timeout=1, xonxoff=flow == 'xonxoff', rtscts=flow == 'rtscts', dsrdtr=flow == 'dsrdtr')
            # Discard data left in the receive buffer before this connection.
            transport.reset_input_buffer()
            # A prior live test (for example, photocell status) keeps streaming
            # until the device receives Enter. Start each session at its prompt.
            enter = c.get('enter', '\r').encode('ascii')
            if transport.write(enter) != len(enter):
                raise IOError('No se pudo enviar Intro para detener la lectura anterior.')
            # The device can finish one final live-status frame before it
            # returns to its prompt. Drain that frame so a new session opens
            # with a clean terminal instead of displaying the previous test.
            startup_data = bytearray()
            prompt_seen = False
            deadline = time.monotonic() + 1.5
            while time.monotonic() < deadline:
                incoming = transport.read(1)
                if incoming:
                    startup_data.extend(incoming)
                    if b'>' in incoming:
                        prompt_seen = True
                        break
            if prompt_seen:
                transport.reset_input_buffer()
            self.transport = transport
            self.active_connection = c
            self.terminal_text = TerminalText()
            self.console.configure(state='normal')
            self.console.delete('1.0', 'end')
            self.console.configure(state='disabled')
            self.session += 1
            session = self.session
            self.reader_stop = threading.Event()
            threading.Thread(target=self.receive, args=(transport, self.reader_stop, session), daemon=True).start()
            mode = f"RS-232 · {c['port']} · {c['baudrate']} · {c['bytesize']}{c['parity']}{c['stopbits']:g} · Flujo: {flow}"
            self.status.configure(text=f'Conectado · {mode}')
            self.connect_btn.configure(text='Desconectar')
            self.log('INFO', f'{self.current()["name"]} · {mode}')
            self.log('TX', f'{enter!r} · Intro inicial para detener la lectura anterior')
            if not prompt_seen and startup_data:
                self.events.put((session, 'RX', startup_data.decode('cp850', errors='replace')))
                self.log('INFO', 'No se detectó el prompt durante la limpieza inicial; revisa la respuesta del equipo.')
            self.controls()
        except Exception as exc:
            messagebox.showerror('No se pudo conectar', f'{exc}\nCierra HyperTerminal si está utilizando ese puerto.')

    def disconnect(self):
        self.cancel.set()
        self.manual_queue.clear()
        self.reader_stop.set()
        self.session += 1
        transport, self.transport = self.transport, None
        self.active_connection = None
        if transport:
            transport.close()
        self.busy = False
        self.active_task_kind = None
        self.connect_btn.configure(text='Conectar')
        self.status.configure(text='Desconectado')
        self.controls()
        self.log('INFO', 'Desconectado')

    def receive(self, transport, stopped, session):
        while not stopped.wait(0.025):
            try:
                data = transport.read(4096)
                if data:
                    self.events.put((session, 'RX', data.decode('cp850', errors='replace')))
            except Exception as exc:
                if not stopped.is_set():
                    self.events.put((session, 'ERROR', str(exc)))
                return

    def start_steps(self, name, steps, kind='operation'):
        if self.transport is None or self.busy:
            return
        self.busy = True
        self.active_task_kind = kind
        self.cancel = threading.Event()
        transport, cancel, session = self.transport, self.cancel, self.session
        enter = self.active_connection.get('enter', '\r')
        self.controls()
        self.log('INICIO', name)
        def worker():
            try:
                def write(data):
                    if transport.write(data) != len(data):
                        raise IOError('Envío incompleto')
                    self.events.put((session, 'TX', repr(data)))
                finished = run_steps(steps, enter, write, cancel)
                self.events.put((session, 'DONE', 'Comandos enviados.' if finished else 'Secuencia cancelada; no se deshacen comandos ya enviados.'))
            except Exception as exc:
                self.events.put((session, 'ERROR', str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def execute(self):
        selection = self.ops.curselection()
        if not selection or self.busy or self.transport is None:
            return
        op = self.current()['operations'][selection[0]]
        if self.confirm_operations.get() and op.get('confirm') and not messagebox.askyesno(op['name'], op['confirm'], parent=self):
            return
        parameters = parameters_for(op['steps'])
        if parameters:
            values = self.ask_parameters(op['name'], parameters)
            if values is None:
                return
            steps = resolve_steps(op['steps'], values)
        else:
            steps = op['steps']
        self.start_steps(op['name'], steps)

    def execute_from_list(self, event):
        index = self.ops.nearest(event.y)
        bounds = self.ops.bbox(index)
        if bounds is None or not bounds[1] <= event.y < bounds[1] + bounds[3]:
            return 'break'
        self.ops.selection_clear(0, 'end')
        self.ops.selection_set(index)
        self.ops.activate(index)
        self.preview()
        self.execute()
        return 'break'

    def ask_parameters(self, action_name, parameters):
        dialog = tk.Toplevel(self)
        dialog.withdraw()
        dialog.title(f'Valores para {action_name}')
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Introduce los valores antes de enviar la secuencia.').grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 10))
        entries = {}
        for row, step in enumerate(parameters, start=1):
            name = step['parameter']
            ttk.Label(frame, text=name).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=4)
            variable = tk.StringVar(value=step['default'])
            entry = ttk.Entry(frame, textvariable=variable, width=28)
            entry.grid(row=row, column=1, sticky='ew', pady=4)
            entries[name] = (variable, entry, step['kind'])
        result = {'values': None}
        def accept(event=None):
            values = {name: var.get() for name, (var, _, _) in entries.items()}
            try:
                resolve_steps([step for step in parameters], values)
            except ValueError as exc:
                messagebox.showerror('Valor inválido', str(exc), parent=dialog)
                return
            result['values'] = values
            dialog.destroy()
        buttons = ttk.Frame(frame)
        buttons.grid(row=len(parameters) + 1, column=0, columnspan=2, sticky='e', pady=(12, 0))
        ttk.Button(buttons, text='Cancelar', command=dialog.destroy).pack(side='right')
        ttk.Button(buttons, text='Ejecutar', command=accept).pack(side='right', padx=(0, 8))
        dialog.bind('<Return>', accept)
        dialog.bind('<Escape>', lambda _: dialog.destroy())
        dialog.transient(self)
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - dialog.winfo_reqwidth()) // 2
        y = self.winfo_y() + (self.winfo_height() - dialog.winfo_reqheight()) // 2
        dialog.geometry(f'+{x}+{y}')
        dialog.deiconify()
        dialog.grab_set()
        entries[parameters[0]['parameter']][1].focus_set()
        dialog.wait_window()
        return result['values']

    def send_manual(self):
        if self.transport is None:
            return
        text = self.manual.get()
        try:
            steps = manual_text_steps(text, self.add_enter.get())
        except UnicodeEncodeError:
            messagebox.showerror('Texto inválido', 'Los comandos deben ser ASCII.')
            return
        if not steps:
            return
        self.manual_queue.append(steps)
        if self.busy:
            if self.active_task_kind == 'operation':
                self.cancel.set()
        else:
            self.start_next_manual()
        self.manual.delete(0, 'end')
        self.manual.focus_set()

    def start_next_manual(self):
        if self.transport is not None and not self.busy and self.manual_queue:
            self.start_steps('Envío manual', self.manual_queue.pop(0), kind='manual')

    def send_from_input(self):
        if self.manual.get():
            self.send_manual()
        else:
            self.send_enter()
        self.manual.focus_set()

    def handle_enter(self, event):
        # Keep modal editors' Enter key local (for example, an action name).
        # Tk may report internal combobox/popdown widgets as Tcl path strings.
        widget = event.widget
        if not isinstance(widget, tk.Misc) or widget.winfo_toplevel() is not self:
            return
        if widget is self.manual:
            self.send_from_input()
        elif widget is self.ops:
            self.execute()
        else:
            self.send_enter()
        return 'break'

    def send_enter(self):
        """Send Enter immediately; interrupt any remaining sequence steps."""
        if self.transport is None:
            return
        self.manual_queue.clear()
        if self.busy:
            self.cancel.set()
        try:
            enter = self.active_connection.get('enter', '\r')
            payload = enter.encode('ascii')
            if self.transport.write(payload) != len(payload):
                raise IOError('Envío incompleto')
            self.log('TX', repr(payload))
        except Exception as exc:
            self.log('ERROR', str(exc))
            self.disconnect()

    def stop(self):
        self.manual_queue.clear()
        self.cancel.set()

    def poll(self):
        for _ in range(200):
            try:
                session, kind, text = self.events.get_nowait()
            except queue.Empty:
                break
            if session != self.session:
                continue
            self.log(kind, text)
            if kind == 'DONE':
                self.busy = False
                self.active_task_kind = None
                if self.manual_queue:
                    self.start_next_manual()
                else:
                    self.controls()
            elif kind == 'ERROR':
                self.disconnect()
        self.after(60, self.poll)

    def save_log(self):
        path = filedialog.asksaveasfilename(defaultextension='.txt', initialfile=f'TM App-{datetime.now():%Y%m%d-%H%M%S}.txt', filetypes=[('Registro de texto', '*.txt')])
        if path:
            try:
                Path(path).write_text(''.join(self.history), encoding='utf-8')
            except OSError as exc:
                messagebox.showerror('No se pudo guardar', str(exc))

    def export_profiles(self):
        picker = ProfilePicker(self, self.profiles, 'export')
        self.wait_window(picker)
        if picker.result is None:
            return
        path = filedialog.asksaveasfilename(
            title='Exportar equipos y acciones',
            defaultextension='.json',
            initialfile='tm-app-perfiles.json',
            filetypes=[('Perfiles TM App', '*.json')],
        )
        if not path:
            return
        try:
            shared = select_profiles(self.profiles, picker.result)
            Path(path).write_text(json.dumps(shared, ensure_ascii=False, indent=2), encoding='utf-8')
            self.log('INFO', f'Perfiles exportados: {path}')
        except (OSError, ValueError) as exc:
            messagebox.showerror('No se pudo exportar', str(exc))

    def import_profiles(self):
        if self.transport is not None:
            return
        path = filedialog.askopenfilename(
            title='Importar equipos y acciones',
            filetypes=[('Perfiles TM App', '*.json'), ('Todos los archivos', '*.*')],
        )
        if not path:
            return
        try:
            shared = read_profile(path)
            upgrade_legacy_passwords(shared)
            picker = ProfilePicker(self, shared, 'import', local_profiles=self.profiles)
            self.wait_window(picker)
            if picker.result is None:
                return
            merged, conflicts = merge_selected_profiles(self.profiles, shared, picker.result, picker.destinations)
            if conflicts['machines'] or conflicts['operations']:
                details = []
                if conflicts['machines']:
                    names = ', '.join(conflicts['machines'][:5])
                    details.append(f"Equipos completos que se sustituirán ({len(conflicts['machines'])}): {names}")
                if conflicts['operations']:
                    names = ', '.join(f'{machine} / {operation}' for machine, operation in conflicts['operations'][:5])
                    details.append(f"Acciones que se sustituirán ({len(conflicts['operations'])}): {names}")
                if not messagebox.askyesno(
                    'Confirmar sustituciones',
                    '\n'.join(details) + '\n\nLos demás equipos y acciones locales se conservarán. ¿Continuar?',
                ):
                    return
            backup = self.profile_path.with_name('machines.backup.json')
            backup_temp = backup.with_suffix('.tmp')
            backup_temp.write_bytes(self.profile_path.read_bytes())
            backup_temp.replace(backup)
            self.store_profiles(merged, self.machine.get())
            self.log('INFO', f'Perfiles importados: {path} · Copia anterior: {backup}')
        except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
            messagebox.showerror('No se pudieron importar los perfiles', str(exc))

    def edit_profiles(self):
        if self.transport is not None:
            return
        return ProfileEditor(self, self.profiles, self.machine.get(), self.store_profiles)

    def store_profiles(self, data, selected_name):
        temp = self.profile_path.with_suffix('.tmp')
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(self.profile_path)
        self.profiles = data
        self.machine.configure(values=[m['name'] for m in data['machines']])
        self.machine.set(selected_name)
        self.change_machine()
        self.log('INFO', 'Equipos y acciones guardados')

    def close_app(self):
        if self.busy and not messagebox.askyesno('Cerrar', 'Hay una secuencia en curso. ¿Cancelar y cerrar?'):
            return
        self.disconnect()
        self.destroy()


if __name__ == '__main__':
    App().mainloop()
