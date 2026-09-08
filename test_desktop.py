"""Desktop protocol validation without reading or changing a user's desktop."""
import copy
import time
import unittest
from unittest.mock import Mock, patch

try:
    from desktop_worker import Desktop, Portal
except ModuleNotFoundError as exc:
    raise unittest.SkipTest('Run desktop protocol tests with /usr/bin/python3 for GI bindings') from exc


class Node:
    def __init__(self, text='initial', role='entry', active=True):
        self.text = text
        self.role = role
        self.active = active
        self.writes = []

    def get_editable_text_iface(self):
        return self

    def set_text_contents(self, text):
        self.writes.append(text)
        self.text = text
        return True

    def get_text_iface(self):
        return self

    def get_text(self, start, end):
        return self.text[start:end]

    def get_character_count(self):
        return len(self.text)

    def get_role(self):
        return 0


class FakeDesktop(Desktop):
    def describe(self, node):
        return {'text': node.text, 'role': node.role, 'interfaces': ['EditableText', 'Text'],
                'states': ['showing', 'sensitive'] + (['active'] if node.active else [])}

    def observe(self, **kwargs):
        self.snapshot = {'snapshot_id': 'next', 'captured_at': time.time(), 'elements': []}
        return self.snapshot


class DesktopTests(unittest.TestCase):
    def setUp(self):
        p = patch('desktop_worker.Atspi.Text.get_text', side_effect=lambda node, start, end: node.get_text(start, end))
        p.start(); self.addCleanup(p.stop)
        p = patch('desktop_worker.Atspi.Text.get_character_count', side_effect=lambda node: node.get_character_count())
        p.start(); self.addCleanup(p.stop)
        self.d = FakeDesktop(Mock())
        self.node = Node()
        self.window = Node(role='window')
        self.d.snapshot = {'snapshot_id': 'now', 'captured_at': time.time()}
        self.d.entries['e1'] = (self.node, self.d.signature(self.d.describe(self.node)), self.window, 'test')

    def test_stale_snapshot_never_mutates(self):
        with self.assertRaisesRegex(ValueError, 'Stale snapshot'):
            self.d.act('old', [{'kind': 'set_text', 'element': 'e1', 'text': 'bad'}])
        self.assertEqual(self.node.writes, [])

    def test_stale_element_and_inactive_window_are_rejected(self):
        self.node.text = 'changed elsewhere'
        with self.assertRaisesRegex(ValueError, 'Stale element'):
            self.d.resolve('e1')
        self.node.text = 'initial'
        self.window.active = False
        with self.assertRaisesRegex(ValueError, 'not active'):
            self.d.resolve('e1')

    def test_invalid_later_action_prevents_first_mutation(self):
        actions = [{'kind': 'set_text', 'element': 'e1', 'text': 'ok'}, {'kind': 'click', 'x': 2, 'y': .5}]
        with self.assertRaises(ValueError):
            self.d.act('now', actions)
        self.assertEqual(self.node.writes, [])

    @patch('desktop_worker.pump')
    def test_text_is_verified_by_readback_and_snapshot_is_consumed(self, _):
        r = self.d.act('now', [{'kind': 'set_text', 'element': 'e1', 'text': 'Olá, ação'}], wait_ms=0)
        self.assertTrue(r['ok'])
        self.assertTrue(r['results'][0]['verified'])
        with self.assertRaisesRegex(ValueError, 'Stale snapshot'):
            self.d.act('now', [{'kind': 'set_text', 'element': 'e1', 'text': 'again'}])

    @patch('desktop_worker.pump')
    def test_partial_batch_stops_when_target_changes(self, _):
        r = self.d.act('now', [{'kind': 'set_text', 'element': 'e1', 'text': 'first'},
                               {'kind': 'set_text', 'element': 'e1', 'text': 'second'}], wait_ms=0)
        self.assertFalse(r['ok'])
        self.assertEqual(r['completed'], 1)
        self.assertEqual(self.node.writes, ['first'])

    def test_raw_input_requires_matching_observed_monitor(self):
        with self.assertRaisesRegex(ValueError, 'screenshot observation'):
            self.d.act('now', [{'kind': 'click', 'x': .5, 'y': .5}], session_id='session')
        self.d.portal.perform.assert_not_called()

    def test_expired_observation_rejected(self):
        self.d.snapshot['captured_at'] -= 121
        with self.assertRaisesRegex(ValueError, 'expired'):
            self.d.act('now', [{'kind': 'set_text', 'element': 'e1', 'text': 'bad'}])

    def test_payload_limits_and_no_code_field(self):
        for action in [{'kind': 'click', 'x': float('nan'), 'y': 0},
                       {'kind': 'click', 'x': True, 'y': 0},
                       {'kind': 'key', 'keys': ['CTRL', 'CTRL']},
                       {'kind': 'key', 'keys': ['not-a-key']},
                       {'kind': 'set_text', 'element': 'e1', 'text': 'x'*4001},
                       {'kind': 'focus', 'element': 'e1', 'code': 'bad'}]:
            with self.subTest(action=str(action)[:80]), self.assertRaises(ValueError):
                self.d.validate_actions([action])

    def test_portal_revocation_and_session_identity(self):
        p = Portal.__new__(Portal)
        p.state, p.session_id = 'closed', 'a'
        with self.assertRaises(ValueError):
            p.require('a')
        p.state = 'active'
        with self.assertRaises(ValueError):
            p.require('b')

    def test_keys_unicode_and_modifiers(self):
        self.assertEqual(Portal.keysyms(['CTRL', 's']), [0xffe3, 115])
        with self.assertRaises(ValueError):
            Portal.keysyms(['€'])
        self.d.validate_actions([{'kind': 'type_text', 'text': 'Olá €'}])


if __name__ == '__main__':
    unittest.main()
