"""Profile validation and interruptible command execution, independent of the UI."""
import copy
import json
import threading
from pathlib import Path


class TerminalText:
    """Plain serial terminal: CR returns to column zero; LF advances a line.

    feed returns the screen contents, preserving the cursor between chunks.
    This is not an ANSI/VT escape-sequence emulator.
    """
    def __init__(self):
        self.lines = [[]]
        self.row = 0
        self.column = 0

    def feed(self, text):
        for char in text:
            if char == '\r':
                self.column = 0
            elif char == '\n':
                self.row += 1
                while self.row >= len(self.lines):
                    self.lines.append([])
                self.column = 0
                if len(self.lines) > 2000:
                    del self.lines[0]
                    self.row -= 1
            elif char == '\v':
                # This controller uses CR+VT after its second status row to
                # return to the first row and refresh the two live readings.
                self.row = max(0, self.row - 1)
                self.column = 0
            elif char == '\b':
                self.column = max(0, self.column - 1)
            else:
                line = self.lines[self.row]
                if self.column < len(line):
                    line[self.column] = char
                else:
                    line.append(char)
                self.column += 1
        return '\n'.join(''.join(line) for line in self.lines)


def validate(data):
    if not isinstance(data, dict) or not isinstance(data.get('machines'), list) or not data['machines']:
        raise ValueError('Debe existir una lista machines con al menos una máquina.')
    names = set()
    for machine in data['machines']:
        name = machine.get('name')
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError('Cada máquina necesita un nombre único.')
        names.add(name)
        conn = machine['connection']
        if not isinstance(conn['baudrate'], int) or conn['baudrate'] <= 0:
            raise ValueError('Velocidad inválida.')
        if conn['bytesize'] not in (5, 6, 7, 8) or conn['parity'] not in ('N', 'E', 'O', 'M', 'S') or conn['stopbits'] not in (1, 1.5, 2):
            raise ValueError('Parámetros de conexión inválidos.')
        if conn.get('flow', 'none') not in ('none', 'rtscts', 'xonxoff', 'dsrdtr'):
            raise ValueError('Control de flujo inválido.')
        if conn.get('enter', '\r') not in ('\r', '\n', '\r\n'):
            raise ValueError('Enter debe ser CR, LF o CRLF.')
        operations = machine['operations']
        if not isinstance(operations, list):
            raise ValueError('operations debe ser una lista.')
        op_names = set()
        for op in operations:
            if not isinstance(op.get('name'), str) or not op['name'].strip() or op['name'] in op_names:
                raise ValueError('Cada operación necesita un nombre único dentro de su máquina.')
            op_names.add(op['name'])
            if not isinstance(op.get('steps'), list) or not op['steps']:
                raise ValueError('Cada operación necesita pasos.')
            parameters = {}
            for step in op['steps']:
                if ('send' in step) == ('parameter' in step):
                    raise ValueError('Cada paso necesita una tecla o un valor variable.')
                if 'send' in step:
                    if not isinstance(step['send'], str):
                        raise ValueError('La tecla debe ser texto.')
                    step['send'].replace('<ENTER>', conn.get('enter', '\r')).encode('ascii')
                else:
                    validate_parameter_step(step)
                    name = step['parameter']
                    definition = (step['kind'], step['default'])
                    if name in parameters and parameters[name] != definition:
                        raise ValueError(f'El valor variable «{name}» tiene definiciones distintas.')
                    parameters[name] = definition
                delay = step.get('delay_ms', 0)
                if isinstance(delay, bool) or not isinstance(delay, (int, float)) or not 0 <= delay <= 60000:
                    raise ValueError('Las pausas deben estar entre 0 y 60000 ms.')
    return data


def validate_parameter_value(value, kind):
    if not isinstance(value, str) or not value or not value.isascii() or not value.isprintable() or '<ENTER>' in value:
        raise ValueError('El valor debe contener texto ASCII visible, sin Intro ni controles.')
    if kind == 'number' and not all('0' <= char <= '9' for char in value):
        raise ValueError('El valor debe contener solo dígitos del 0 al 9.')
    if kind not in ('number', 'text'):
        raise ValueError('Tipo de valor variable no válido.')
    return value


def validate_parameter_step(step):
    if not isinstance(step.get('parameter'), str) or not step['parameter'].strip():
        raise ValueError('El valor variable necesita un nombre.')
    validate_parameter_value(step.get('default'), step.get('kind'))
    return step


def parameters_for(steps):
    return list({step['parameter']: step for step in steps if 'parameter' in step}.values())


def resolve_steps(steps, values):
    resolved = []
    for step in steps:
        if 'parameter' in step:
            name = step['parameter']
            value = validate_parameter_value(values[name], step['kind'])
            resolved.append({'send': value, 'delay_ms': step.get('delay_ms', 0)})
        else:
            resolved.append(copy.deepcopy(step))
    return resolved


def upgrade_legacy_machaque(profiles):
    """Upgrade only the exact bundled macro, preserving user-edited versions."""
    original = ['<ENTER>', 'M', '0', '1', '<ENTER>', '50', '<ENTER>']
    delays = [300, 200, 200, 200, 200, 200, 0]
    for machine in profiles['machines']:
        if machine['name'] != 'VP1994+':
            continue
        for op in machine['operations']:
            if op['name'] != 'Machaque Título':
                continue
            if op['steps'] != [{'send': key, 'delay_ms': delay} for key, delay in zip(original, delays)]:
                return False
            op['steps'][5] = {'parameter': 'Cantidad', 'default': '50', 'kind': 'number', 'delay_ms': 200}
            return True
    return False


def upgrade_legacy_passwords(profiles):
    """Pace factory ABCD sequences while leaving other actions untouched."""
    changed = False
    names = {'Reset', 'Borrar Estadísticas', 'Borrar Telecarga'}
    for machine in profiles['machines']:
        if machine['name'] != 'VP1994+':
            continue
        for op in machine['operations']:
            if op['name'] not in names:
                continue
            steps = []
            for step in op['steps']:
                if step == {'send': 'ABCD', 'delay_ms': 200}:
                    steps.extend({'send': char, 'delay_ms': 200} for char in 'ABCD')
                    changed = True
                else:
                    steps.append(step)
            op['steps'] = steps
    return changed


def read_profile(path):
    return validate(json.loads(Path(path).read_text(encoding='utf-8-sig')))


def merge_profiles(local, shared):
    """Add shared machines and replace exact-name matches, preserving others."""
    validate(local)
    validate(shared)
    merged = copy.deepcopy(local)
    positions = {machine['name']: index for index, machine in enumerate(merged['machines'])}
    replaced = []
    for machine in shared['machines']:
        name = machine['name']
        if name in positions:
            merged['machines'][positions[name]] = copy.deepcopy(machine)
            replaced.append(name)
        else:
            positions[name] = len(merged['machines'])
            merged['machines'].append(copy.deepcopy(machine))
    return validate(merged), replaced


def select_profiles(profiles, selection):
    """Select entire machines (None) or named operations (set of names)."""
    validate(profiles)
    if not selection:
        raise ValueError('Selecciona al menos un equipo o una acción.')
    source = {machine['name']: machine for machine in profiles['machines']}
    machines = []
    for name, operations in selection.items():
        if name not in source:
            raise ValueError(f'Equipo desconocido: {name}')
        machine = copy.deepcopy(source[name])
        if operations is not None:
            names = {op['name'] for op in machine['operations']}
            if not operations or not set(operations) <= names:
                raise ValueError(f'Acciones inválidas para {name}')
            machine['operations'] = [op for op in machine['operations'] if op['name'] in operations]
        machines.append(machine)
    return validate({'format': 'tm-app-perfiles', 'version': 1, 'machines': machines})


def suggest_profile_destinations(local, shared):
    """Suggest exact or unambiguous matches ignoring case and whitespace."""
    names = [machine['name'] for machine in local['machines']]
    normalized = {}
    for name in names:
        normalized.setdefault(' '.join(name.split()).casefold(), []).append(name)
    result = {}
    for machine in shared['machines']:
        name = machine['name']
        matches = normalized.get(' '.join(name.split()).casefold(), [])
        result[name] = name if name in names else matches[0] if len(matches) == 1 else None
    return result


def resolve_profile_destinations(local, shared, selection, destinations=None):
    """Resolve source names to existing destinations or explicit new machines."""
    local_names = {machine['name'] for machine in local['machines']}
    source_names = {machine['name'] for machine in shared['machines']}
    result = {}
    grouped = {}
    for source in selection:
        if source not in source_names:
            raise ValueError(f'Equipo desconocido: {source}')
        if destinations is None:
            target = source if source in local_names else None
        else:
            if source not in destinations:
                raise ValueError(f'Selecciona un destino para {source}.')
            target = destinations[source]
        if target is None:
            if source in local_names:
                raise ValueError(f'Ya existe el equipo «{source}». Elige su perfil local como destino.')
            target = source
        elif not isinstance(target, str) or target not in local_names:
            raise ValueError(f'El destino de «{source}» no es un equipo local válido.')
        result[source] = target
        grouped.setdefault(target, []).append(source)
    for target, sources in grouped.items():
        if len(sources) > 1 and any(selection[source] is None for source in sources):
            raise ValueError(f'Varios equipos apuntan a «{target}». Selecciona acciones concretas para combinarlos o impórtalos por separado.')
    return result


def merge_selected_profiles(local, shared, selection, destinations=None):
    """Merge chosen operations without changing an existing machine's connection."""
    selected = select_profiles(shared, selection)
    validate(local)
    targets = resolve_profile_destinations(local, shared, selection, destinations)
    merged = copy.deepcopy(local)
    positions = {machine['name']: index for index, machine in enumerate(merged['machines'])}
    conflicts = {'machines': [], 'operations': []}
    for machine in selected['machines']:
        source_name = machine['name']
        name = targets[source_name]
        machine['name'] = name
        if name not in positions:
            positions[name] = len(merged['machines'])
            merged['machines'].append(machine)
        elif selection[source_name] is None:
            conflicts['machines'].append(name)
            merged['machines'][positions[name]] = machine
        else:
            target = merged['machines'][positions[name]]['operations']
            operation_positions = {op['name']: index for index, op in enumerate(target)}
            for operation in machine['operations']:
                operation_name = operation['name']
                if operation_name in operation_positions:
                    conflicts['operations'].append((name, operation_name))
                    target[operation_positions[operation_name]] = operation
                else:
                    operation_positions[operation_name] = len(target)
                    target.append(operation)
    return validate(merged), conflicts


def run_steps(steps, enter, write, cancel):
    for step in steps:
        if cancel.is_set():
            return False
        write(step['send'].replace('<ENTER>', enter).encode('ascii'))
        if cancel.wait(step.get('delay_ms', 0) / 1000):
            return False
    return True


def manual_text_steps(value, append_enter=False, delay_ms=200):
    """Turn typed text into paced keystrokes without interpreting its contents."""
    value.encode('ascii')
    steps = [
        {'send': char, 'delay_ms': delay_ms if index < len(value) - 1 or append_enter else 0}
        for index, char in enumerate(value)
    ]
    if append_enter:
        steps.append({'send': '<ENTER>', 'delay_ms': 0})
    return steps


class Simulator:
    """Echo only: never pretends that a hardware test passed."""
    def __init__(self):
        self.buffer = bytearray()
        self.lock = threading.Lock()

    def write(self, data):
        with self.lock:
            self.buffer.extend(b'[SIM eco] ' + repr(data).encode('ascii') + b'\r\n')
        return len(data)

    def read(self, size=4096):
        with self.lock:
            data = bytes(self.buffer[:size])
            del self.buffer[:size]
            return data

    def close(self):
        pass
