import threading
import copy
import unittest
import serial
from core import read_profile, merge_profiles, select_profiles, merge_selected_profiles, suggest_profile_destinations, run_steps, manual_text_steps, Simulator, validate, TerminalText, parameters_for, resolve_steps, upgrade_legacy_machaque, upgrade_legacy_passwords
from editor import key_command, delay_value


class Tests(unittest.TestCase):
    def test_import_destination_suggestions_do_not_guess_ambiguous_names(self):
        local = read_profile('machines.json')
        shared = copy.deepcopy(local)
        shared['machines'][0]['name'] = '  vp1994+  '
        self.assertEqual(suggest_profile_destinations(local, shared), {'  vp1994+  ': 'VP1994+'})
        local['machines'].append(dict(copy.deepcopy(local['machines'][0]), name='Vp1994+'))
        self.assertIsNone(suggest_profile_destinations(local, shared)['  vp1994+  '])
        shared['machines'][0]['name'] = 'VP1994+'
        self.assertEqual(suggest_profile_destinations(local, shared)['VP1994+'], 'VP1994+')

    def test_import_actions_into_differently_named_destination(self):
        local = read_profile('machines.json')
        shared = copy.deepcopy(local)
        shared['machines'][0]['name'] = 'VP 1994 Plus'
        shared['machines'][0]['connection']['baudrate'] = 9600
        shared['machines'][0]['operations'][0]['steps'] = [{'send': 'X', 'delay_ms': 150}]
        selected = {'VP 1994 Plus': {'Borrar Telecarga'}}
        merged, conflicts = merge_selected_profiles(local, shared, selected, {'VP 1994 Plus': 'VP1994+'})
        self.assertEqual([m['name'] for m in merged['machines']], ['VP1994+'])
        self.assertEqual(merged['machines'][0]['connection'], local['machines'][0]['connection'])
        self.assertEqual(len(merged['machines'][0]['operations']), len(local['machines'][0]['operations']))
        self.assertEqual(merged['machines'][0]['operations'][0]['steps'], [{'send': 'X', 'delay_ms': 150}])
        self.assertEqual(conflicts['operations'], [('VP1994+', 'Borrar Telecarga')])
        self.assertEqual(shared['machines'][0]['name'], 'VP 1994 Plus')

    def test_import_complete_destination_preserves_local_name_and_other_machines(self):
        local = read_profile('machines.json')
        local['machines'].append(dict(copy.deepcopy(local['machines'][0]), name='Otro equipo'))
        shared = read_profile('machines.json')
        shared['machines'][0]['name'] = 'Alias'
        shared['machines'][0]['connection']['baudrate'] = 9600
        shared['machines'][0]['operations'] = shared['machines'][0]['operations'][:1]
        merged, conflicts = merge_selected_profiles(local, shared, {'Alias': None}, {'Alias': 'VP1994+'})
        self.assertEqual([m['name'] for m in merged['machines']], ['VP1994+', 'Otro equipo'])
        self.assertEqual(merged['machines'][0]['connection']['baudrate'], 9600)
        self.assertEqual(len(merged['machines'][0]['operations']), 1)
        self.assertEqual(merged['machines'][1], local['machines'][1])
        self.assertEqual(conflicts['machines'], ['VP1994+'])

    def test_import_new_destination_and_invalid_destinations(self):
        local = read_profile('machines.json')
        shared = copy.deepcopy(local)
        shared['machines'][0]['name'] = 'Alias'
        merged, conflicts = merge_selected_profiles(local, shared, {'Alias': None}, {'Alias': None})
        self.assertEqual([m['name'] for m in merged['machines']], ['VP1994+', 'Alias'])
        self.assertEqual(conflicts, {'machines': [], 'operations': []})
        for targets in ({}, {'Alias': 'Inexistente'}):
            with self.assertRaises(ValueError):
                merge_selected_profiles(local, shared, {'Alias': None}, targets)
        with self.assertRaises(ValueError):
            merge_selected_profiles(local, local, {'VP1994+': None}, {'VP1994+': None})

    def test_import_multiple_sources_into_one_destination(self):
        local = read_profile('machines.json')
        shared = copy.deepcopy(local)
        shared['machines'][0]['name'] = 'Alias uno'
        shared['machines'].append(dict(copy.deepcopy(shared['machines'][0]), name='Alias dos'))
        shared['machines'][0]['operations'][0]['name'] = 'Acción nueva uno'
        shared['machines'][1]['operations'][0]['name'] = 'Acción nueva dos'
        targets = {'Alias uno': 'VP1994+', 'Alias dos': 'VP1994+'}
        selected = {'Alias uno': {'Acción nueva uno'}, 'Alias dos': {'Acción nueva dos'}}
        merged, conflicts = merge_selected_profiles(local, shared, selected, targets)
        self.assertEqual(len(merged['machines'][0]['operations']), len(local['machines'][0]['operations']) + 2)
        self.assertEqual(conflicts, {'machines': [], 'operations': []})
        selected['Alias uno'] = None
        with self.assertRaises(ValueError):
            merge_selected_profiles(local, shared, selected, targets)

    def test_import_one_action_preserves_existing_machine(self):
        local = read_profile('machines.json')
        shared = copy.deepcopy(local)
        shared['machines'][0]['connection']['baudrate'] = 9600
        shared['machines'][0]['operations'][0]['steps'] = [{'send': 'X', 'delay_ms': 150}]
        selection = {'VP1994+': {'Borrar Telecarga'}}
        exported = select_profiles(shared, selection)
        self.assertEqual(len(exported['machines'][0]['operations']), 1)
        merged, conflicts = merge_selected_profiles(local, exported, selection)
        self.assertEqual(conflicts, {'machines': [], 'operations': [('VP1994+', 'Borrar Telecarga')]})
        self.assertEqual(merged['machines'][0]['connection']['baudrate'], 2400)
        self.assertEqual(len(merged['machines'][0]['operations']), len(local['machines'][0]['operations']))
        self.assertEqual(merged['machines'][0]['operations'][0]['steps'], [{'send': 'X', 'delay_ms': 150}])
        self.assertNotEqual(local['machines'][0]['operations'][0]['steps'], merged['machines'][0]['operations'][0]['steps'])

    def test_shared_profiles_replace_matches_and_keep_other_machines(self):
        local = read_profile('machines.json')
        local['machines'].append(dict(copy.deepcopy(local['machines'][0]), name='Equipo local'))
        shared = copy.deepcopy(local)
        shared['machines'] = [shared['machines'][0], dict(copy.deepcopy(shared['machines'][0]), name='Equipo nuevo')]
        shared['machines'][0]['operations'][0]['name'] = 'Acción compartida'
        merged, replaced = merge_profiles(local, shared)
        self.assertEqual(replaced, ['VP1994+'])
        self.assertEqual([machine['name'] for machine in merged['machines']], ['VP1994+', 'Equipo local', 'Equipo nuevo'])
        self.assertEqual(merged['machines'][0]['operations'][0]['name'], 'Acción compartida')
        self.assertEqual(local['machines'][0]['operations'][0]['name'], 'Borrar Telecarga')

    def test_recorded_keys(self):
        self.assertEqual(key_command('Return', '\r'), '<ENTER>')
        self.assertEqual(key_command('Tab', '\t'), '\t')
        self.assertEqual(key_command('BackSpace', '\b'), '\b')
        self.assertEqual(key_command('V', 'V'), 'V')
        self.assertEqual(key_command('a', '\x01', control=True), '\x01')
        self.assertIsNone(key_command('Shift_L', ''))
        self.assertIsNone(key_command('Left', ''))
        self.assertIsNone(key_command('ntilde', 'ñ'))

    def test_recording_delays(self):
        self.assertEqual(delay_value('0'), 0)
        self.assertEqual(delay_value('350'), 350)
        for value in ('-1', '60001', 'abc', '1.5'):
            with self.assertRaises(ValueError):
                delay_value(value)
        class Clock:
            def __init__(self):
                self.delays = []
            def is_set(self):
                return False
            def wait(self, delay):
                self.delays.append(delay)
                return False
        clock, sent = Clock(), []
        self.assertTrue(run_steps([{'send': '<ENTER>', 'delay_ms': 350}, {'send': 'V', 'delay_ms': 100}], '\r', sent.append, clock))
        self.assertEqual(sent, [b'\r', b'V'])
        self.assertEqual(clock.delays, [0.35, 0.1])

    def test_manual_text_sends_one_character_at_a_time(self):
        class Clock:
            def __init__(self):
                self.delays = []
            def is_set(self):
                return False
            def wait(self, delay):
                self.delays.append(delay)
                return False
        clock, sent = Clock(), []
        self.assertTrue(run_steps(manual_text_steps('ABCD'), '\r', sent.append, clock))
        self.assertEqual(sent, [b'A', b'B', b'C', b'D'])
        self.assertEqual(clock.delays, [0.2, 0.2, 0.2, 0])
        self.assertEqual([step['send'] for step in manual_text_steps('T', True)], ['T', '<ENTER>'])
        self.assertEqual([step['send'] for step in manual_text_steps('ABCD', True)], ['A', 'B', 'C', 'D', '<ENTER>'])
        self.assertEqual(manual_text_steps('', False), [])

    def test_response_chunks_stay_contiguous(self):
        terminal = TerminalText()
        chunks = ['\n', '\r> ', 'V:Ver ', 'Estado\n', '\rEstado Proc:0\n\r> ']
        for chunk in chunks:
            screen = terminal.feed(chunk)
        self.assertEqual(screen, '\n> V:Ver Estado\nEstado Proc:0\n> ')

    def test_line_breaks_independent_of_chunk_boundaries(self):
        text = 'A\r\nB\n\rC\rD\n\nE'
        whole = TerminalText().feed(text)
        terminal = TerminalText()
        for char in text:
            screen = terminal.feed(char)
        self.assertEqual(screen, whole)
        self.assertEqual(whole, 'A\nB\nD\n\nE')

    def test_live_switch_overwrites_same_line(self):
        terminal = TerminalText()
        header = '> O:Input/Output\r\nOpcion: 0\r\n0:Switch Addr\n\r'
        terminal.feed(header + '00000100')
        self.assertEqual(terminal.feed('\r000'), header.replace('\r', '') + '00000100')
        self.assertEqual(terminal.feed('01000'), header.replace('\r', '') + '00001000')
        self.assertEqual(terminal.feed('\r11111111'), header.replace('\r', '') + '11111111')
        self.assertEqual(terminal.feed('\r\n>'), header.replace('\r', '') + '11111111\n>')

    def test_live_photocells_refresh_two_rows_on_cr_vt(self):
        terminal = TerminalText()
        chunks = [
            'F1:L F2:L F3:L\n\rF4:L FA:L FC:L\r\x0b',
            'F1:H F2:L F3:H\n\rF4:H FA:L FC:H\r\x0b',
            'F1:L F2:H F3:L\n\rF4:L FA:H FC:L\r\x0b',
        ]
        for chunk in chunks:
            screen = terminal.feed(chunk)
        self.assertEqual(screen, 'F1:L F2:H F3:L\nF4:L FA:H FC:L')
        self.assertEqual(len(terminal.lines), 2)

    def test_initial_sequences(self):
        profile = read_profile('machines.json')
        ops = {op['name']: op for op in profile['machines'][0]['operations']}
        self.assertEqual(len(ops), 17)
        self.assertEqual([s['send'] for s in ops['Cálculo PID']['steps']], ['S', '3', '<ENTER>'])
        self.assertEqual([s['delay_ms'] for s in ops['Cálculo PID']['steps']], [200, 200, 200])
        self.assertEqual([s['send'] for s in ops['Test Relé']['steps']], ['<ENTER>', 'O', '9'])
        self.assertEqual([s['send'] for s in ops['Reset']['steps']], ['<ENTER>', 'R', 'A', 'B', 'C', 'D', '<ENTER>'])
        self.assertEqual([s['send'] for s in ops['Leer posición Switch']['steps']], ['<ENTER>', 'O', '0'])
        self.assertEqual([s['send'] for s in ops['Test Motor cinta']['steps']], ['<ENTER>', 'O', '6', 'O', '6', 'O', '6', 'O', '6'])

    def test_variable_value_resolves_before_sending(self):
        steps = [{'send': 'M', 'delay_ms': 200},
                 {'parameter': 'Cantidad', 'default': '50', 'kind': 'number', 'delay_ms': 0},
                 {'send': '<ENTER>', 'delay_ms': 0}]
        self.assertEqual(len(parameters_for(steps)), 1)
        resolved = resolve_steps(steps, {'Cantidad': '75'})
        sent = []
        self.assertTrue(run_steps(resolved, '\r', sent.append, threading.Event()))
        self.assertEqual(sent, [b'M', b'75', b'\r'])
        self.assertEqual(steps[1]['default'], '50')
        for invalid in ('', '-1', '12\r', '<ENTER>', 'ñ'):
            with self.assertRaises(ValueError):
                resolve_steps(steps, {'Cantidad': invalid})

    def test_legacy_machaque_upgrade_preserves_custom_macro(self):
        profile = read_profile('machines.json')
        operation = next(op for op in profile['machines'][0]['operations'] if op['name'] == 'Machaque Título')
        self.assertEqual(operation['steps'][5]['default'], '50')
        operation['steps'][5] = {'send': '50', 'delay_ms': 200}
        self.assertTrue(upgrade_legacy_machaque(profile))
        self.assertEqual(operation['steps'][5]['parameter'], 'Cantidad')
        self.assertFalse(upgrade_legacy_machaque(profile))
        operation['steps'][5] = {'send': '75', 'delay_ms': 200}
        self.assertFalse(upgrade_legacy_machaque(profile))
        self.assertEqual(operation['steps'][5]['send'], '75')

    def test_password_letters_are_paced_and_legacy_profiles_upgrade(self):
        profile = read_profile('machines.json')
        operations = {op['name']: op for op in profile['machines'][0]['operations']}
        for name, count in (('Reset', 1), ('Borrar Estadísticas', 3), ('Borrar Telecarga', 1)):
            steps = operations[name]['steps']
            self.assertEqual(sum(step.get('send') == 'A' for step in steps), count)
            for i, step in enumerate(steps):
                if step.get('send') == 'A':
                    self.assertEqual([(part['send'], part['delay_ms']) for part in steps[i:i+4]],
                                     [(char, 200) for char in 'ABCD'])
        reset = operations['Reset']
        reset['steps'][2:6] = [{'send': 'ABCD', 'delay_ms': 200}]
        self.assertTrue(upgrade_legacy_passwords(profile))
        self.assertFalse(upgrade_legacy_passwords(profile))
        self.assertEqual([s['send'] for s in reset['steps']], ['<ENTER>', 'R', 'A', 'B', 'C', 'D', '<ENTER>'])

    def test_real_serial_api_loopback(self):
        with serial.serial_for_url('loop://', baudrate=2400, timeout=1) as port:
            self.assertTrue(run_steps([{'send': '<ENTER>'}, {'send': 'O'}, {'send': '9'}], '\r', port.write, threading.Event()))
            self.assertEqual(port.read(3), b'\rO9')

    def test_cancel_during_delay(self):
        cancel = threading.Event()
        sent = []
        def write(data):
            sent.append(data)
            cancel.set()
        self.assertFalse(run_steps([{'send': 'A', 'delay_ms': 300}, {'send': 'B'}], '\r', write, cancel))
        self.assertEqual(sent, [b'A'])

    def test_invalid_profile(self):
        profile = read_profile('machines.json')
        profile['machines'][0]['operations'][0]['steps'][0]['delay_ms'] = -1
        with self.assertRaises(ValueError):
            validate(profile)

    def test_simulator_echo(self):
        sim = Simulator()
        sim.write(b'\rO9')
        self.assertEqual(sim.read(), b"[SIM eco] b'\\rO9'\r\n")
        self.assertEqual(sim.read(), b'')


if __name__ == '__main__':
    unittest.main()
