"""Receive-only keyboard test for the physical TM without display."""
from collections import Counter
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import serial
from serial.tools import list_ports

from core import validate
from ui_theme import UI


KEY_ROWS = (('1', '2', '3', 'S'), ('4', '5', '6', 'N'), ('7', '8', '9', 'ESC'),
            ('F1', '0', '↑', 'CR'), ('A', '←', '↓', '→'))
# Special-key bytes captured from a physical TM on 2026-11-02. Arrow bytes are
# raw values, not text decoded as CP850 or ANSI escape sequences.
KEY_CODES = {**{key: ord(key) for key in '0123456789SN'}, 'ESC': 0x1B, 'F1': 0x46,
             'CR': 0x0D, 'A': 0x24, '↑': 0xB2, '←': 0xB4, '↓': 0xB8, '→': 0xB6}
BYTE_KEYS = {value: key for key, value in KEY_CODES.items()}


class TMKeyState:
    def __init__(self):
        self.counts = Counter()
        self.unknown = Counter()

    def feed(self, data):
        events = []
        for value in data:
            key = BYTE_KEYS.get(value)
            if key is None:
                self.unknown[value] += 1
            else:
                self.counts[key] += 1
            events.append((key, value))
        return events


class TMTestWindow(tk.Toplevel):
    def __init__(self, parent, port='COM1'):
        super().__init__(parent)
        self.title('Prueba de TM sin display · TM App')
        self.geometry('900x700')
        self.minsize(820, 620)
        self.configure(bg=UI['canvas'])
        self.transport = None
        self.poll_job = None
        self.key_state = TMKeyState()
        self.history = []
        self.last_key = None
        self.fields = {}
        self.inputs = {}
        root = ttk.Frame(self, padding=16)
        root.pack(fill='both', expand=True)
        ttk.Label(root, text='Prueba de TM sin display', style='Section.TLabel').pack(anchor='w')
        ttk.Label(root, text='Conecta y pulsa las teclas del TM físico. Cada recepción marca su tecla y suma una pulsación.',
                  style='Status.TLabel', wraplength=800).pack(anchor='w', pady=(4, 10))
        connection = ttk.LabelFrame(root, text='Conexión', padding=10)
        connection.pack(fill='x')
        definitions = (
            ('Puerto', 'port', port or 'COM1', ()),
            ('Baudios', 'baudrate', '2400', ('2400', '4800', '9600', '19200', '38400', '57600', '115200')),
            ('Bits de datos', 'bytesize', '8', ('5', '6', '7', '8')),
            ('Paridad', 'parity', 'Ninguna', ('Ninguna', 'Par', 'Impar', 'Marca', 'Espacio')),
            ('Bits de parada', 'stopbits', '1', ('1', '1.5', '2')),
            ('Control de flujo', 'flow', 'Ninguno', ('Ninguno', 'RTS/CTS', 'XON/XOFF', 'DSR/DTR')),
        )
        for index, (label, key, default, options) in enumerate(definitions):
            cell = ttk.Frame(connection)
            cell.grid(row=index // 3, column=index % 3, sticky='ew', padx=6, pady=3)
            connection.columnconfigure(index % 3, weight=1)
            ttk.Label(cell, text=label).pack(anchor='w')
            self.fields[key] = variable = tk.StringVar(value=default)
            self.inputs[key] = entry = ttk.Combobox(cell, textvariable=variable, values=options, width=14,
                                                   state='normal' if key in ('port', 'baudrate') else 'readonly')
            entry.pack(fill='x')
        bar = ttk.Frame(root)
        bar.pack(fill='x', pady=10)
        self.refresh_btn = ttk.Button(bar, text='Actualizar puertos', command=self.refresh_ports)
        self.refresh_btn.pack(side='left')
        self.status = ttk.Label(bar, text='Desconectado · Solo recepción', style='Status.TLabel')
        self.status.pack(side='left', padx=12)
        self.connect_btn = ttk.Button(bar, text='Conectar', command=self.toggle_connection, style='Primary.TButton')
        self.connect_btn.pack(side='right')
        body = ttk.Frame(root)
        body.pack(fill='both', expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)
        keypad = ttk.Frame(body, style='Card.TFrame', padding=10)
        keypad.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        style = ttk.Style(self)
        for name, background, foreground in (
            ('TMKey.TLabel', UI['surface_alt'], UI['muted']),
            ('TMSeen.TLabel', UI['accent_soft'], UI['accent']),
            ('TMLast.TLabel', UI['accent'], UI['surface']),
        ):
            style.configure(name, background=background, foreground=foreground,
                            font=('Segoe UI', 14, 'bold'), padding=5, anchor='center', relief='solid', borderwidth=1)
        self.key_labels = {}
        for row, keys in enumerate(KEY_ROWS):
            keypad.rowconfigure(row, weight=1)
            for column, key in enumerate(keys):
                keypad.columnconfigure(column, weight=1)
                label = ttk.Label(keypad, text=f'{key}\n0', style='TMKey.TLabel', justify='center', width=5)
                label.grid(row=row, column=column, sticky='nsew', padx=3, pady=3)
                self.key_labels[key] = label
        details = ttk.Frame(body, style='Card.TFrame', padding=12)
        details.grid(row=0, column=1, sticky='nsew')
        ttk.Label(details, text='Caracteres recibidos', style='Section.TLabel').pack(anchor='w')
        self.latest = ttk.Label(details, text='Esperando pulsaciones…', style='Card.TLabel')
        self.latest.pack(anchor='w', pady=(6, 10))
        log_frame = ttk.Frame(details, style='Border.TFrame', padding=1)
        log_frame.pack(fill='both', expand=True)
        self.log = tk.Text(log_frame, width=1, height=4, state='disabled', wrap='word', relief='flat',
                           bg=UI['surface_alt'], fg=UI['text'], font=('Consolas', 10), padx=6, pady=5)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.log.pack(fill='both', expand=True)
        self.summary = ttk.Label(root, style='Status.TLabel')
        self.summary.pack(anchor='w', pady=(10, 6))
        footer = ttk.Frame(root)
        footer.pack(fill='x')
        ttk.Button(footer, text='Reiniciar prueba', command=self.reset_test).pack(side='left')
        ttk.Button(footer, text='Guardar registro', command=self.save_log).pack(side='left', padx=8)
        ttk.Button(footer, text='Cerrar', command=self.close).pack(side='right')
        self.update_summary()
        self.refresh_ports()
        self.transient(parent)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f'+{max(0, x)}+{max(0, y)}')
        self.grab_set()

    def refresh_ports(self):
        self.inputs['port'].configure(values=[port.device for port in list_ports.comports()])

    def read_connection(self):
        values = {key: variable.get().strip() for key, variable in self.fields.items()}
        if not values['port']:
            raise ValueError('Selecciona un puerto serie.')
        connection = dict(port=values['port'], baudrate=int(values['baudrate']), bytesize=int(values['bytesize']),
                          parity={'Ninguna': 'N', 'Par': 'E', 'Impar': 'O', 'Marca': 'M', 'Espacio': 'S'}[values['parity']],
                          stopbits=float(values['stopbits']),
                          flow={'Ninguno': 'none', 'RTS/CTS': 'rtscts', 'XON/XOFF': 'xonxoff', 'DSR/DTR': 'dsrdtr'}[values['flow']],
                          enter='\r')
        validate({'machines': [{'name': 'Prueba TM', 'connection': connection, 'operations': []}]})
        return connection

    def connection_controls(self):
        for key, entry in self.inputs.items():
            entry.configure(state='disabled' if self.transport is not None else 'normal' if key in ('port', 'baudrate') else 'readonly')
        self.refresh_btn.configure(state='disabled' if self.transport is not None else 'normal')
        self.connect_btn.configure(text='Desconectar' if self.transport is not None else 'Conectar')

    def toggle_connection(self):
        if self.transport is not None:
            self.disconnect()
            return
        try:
            connection = self.read_connection()
            flow = connection['flow']
            self.transport = serial.Serial(connection['port'], baudrate=connection['baudrate'], bytesize=connection['bytesize'],
                                           parity=connection['parity'], stopbits=connection['stopbits'], timeout=0,
                                           xonxoff=flow == 'xonxoff', rtscts=flow == 'rtscts', dsrdtr=flow == 'dsrdtr')
        except (ValueError, KeyError, OSError, serial.SerialException) as exc:
            messagebox.showerror('No se pudo conectar el TM', str(exc), parent=self)
            return
        self.status.configure(text=f'Conectado · {connection["port"]} · Solo recepción')
        self.connection_controls()
        self.poll_job = self.after(40, self.poll)

    def poll(self):
        self.poll_job = None
        if self.transport is None:
            return
        try:
            waiting = self.transport.in_waiting
            if waiting:
                self.receive(self.transport.read(min(waiting, 4096)))
        except (OSError, serial.SerialException) as exc:
            self.disconnect()
            self.status.configure(text=f'Error de recepción: {exc}')
            return
        self.poll_job = self.after(40, self.poll)

    def receive(self, data):
        for key, value in self.key_state.feed(data):
            if self.last_key is not None:
                self.key_labels[self.last_key].configure(style='TMSeen.TLabel')
            self.last_key = key
            if key is not None:
                self.key_labels[key].configure(text=f'{key}\n{self.key_state.counts[key]}', style='TMLast.TLabel')
            label = key if key is not None else 'Desconocido'
            description = f'{label} · HEX {value:02X} · {bytes((value,))!r}'
            self.latest.configure(text=description)
            line = f'[{datetime.now().strftime("%H:%M:%S.%f")[:-3]}] RX {description}\n'
            self.history.append(line)
            self.log.configure(state='normal')
            self.log.insert('end', line)
            self.log.see('end')
            self.log.configure(state='disabled')
        self.update_summary()

    def update_summary(self):
        self.summary.configure(text=f'{len(self.key_state.counts)}/20 teclas recibidas · '
                               f'{sum(self.key_state.counts.values())} pulsaciones · '
                               f'{sum(self.key_state.unknown.values())} códigos desconocidos')

    def reset_test(self):
        self.key_state = TMKeyState()
        self.last_key = None
        self.history.clear()
        for key, label in self.key_labels.items():
            label.configure(text=f'{key}\n0', style='TMKey.TLabel')
        self.latest.configure(text='Esperando pulsaciones…')
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.configure(state='disabled')
        self.update_summary()

    def save_log(self):
        path = filedialog.asksaveasfilename(parent=self, title='Guardar prueba del TM', defaultextension='.txt',
                                          initialfile='TM-prueba-teclas.txt', filetypes=[('Registro de texto', '*.txt')])
        if path:
            try:
                Path(path).write_text('Prueba de TM sin display\n\n' + ''.join(self.history), encoding='utf-8')
            except OSError as exc:
                messagebox.showerror('No se pudo guardar el registro', str(exc), parent=self)

    def disconnect(self):
        if self.poll_job is not None:
            self.after_cancel(self.poll_job)
            self.poll_job = None
        transport, self.transport = self.transport, None
        if transport is not None:
            transport.close()
        self.status.configure(text='Desconectado · Solo recepción')
        self.connection_controls()

    def close(self):
        self.disconnect()
        self.destroy()
