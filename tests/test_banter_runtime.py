"""Small integrated checks; every provider transport and SC2 sender is fake."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from bot.banter_client import BanterSettings, Worker, request
from bot.banter_runtime import BanterRuntime, GREETING, start_banter


class FakeWorker:
    def __init__(self):
        self.busy = False
        self.requests = []
        self.result = None
        self.closed = False

    def submit(self, payload):
        self.requests.append(payload)
        self.busy = True
        return True

    def poll(self):
        value, self.result = self.result, None
        return value

    def close(self):
        self.closed = True


class BanterTests(unittest.TestCase):
    def test_credentials_worker_and_http_failures_are_separate(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            config = Path(folder) / 'settings'
            config.write_text('DEEPSEEK_API_KEY=decision-only\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                BanterSettings.load(config)
            config.write_text('CHAT_DEEPSEEK_API_KEY=chat-only\n', encoding='utf-8')
            settings = BanterSettings.load(config)
            self.assertEqual(settings.api_key, 'chat-only')
            self.assertNotIn('chat-only', repr(settings))
            with patch('bot.banter_client.requests.post') as post:
                import requests
                post.side_effect = requests.Timeout('chat-only')
                result = request(settings, {'battlefield': {}}, 'character')
                self.assertEqual(result['error'], 'network_timeout')
                self.assertNotIn('chat-only', json.dumps(result))
                self.assertEqual(post.call_args.kwargs['timeout'], (3, 8))
            persona = Path(folder) / 'persona.txt'
            persona.write_text('test character', encoding='utf-8')
            entered, release, finished = threading.Event(), threading.Event(), threading.Event()

            def slow_transport(*args):
                entered.set()
                release.wait(2)
                finished.set()
                return {'ok': True, 'content': 'reply'}

            worker = Worker(settings, persona, transport=slow_transport)
            try:
                self.assertTrue(worker.submit({}))
                self.assertTrue(entered.wait(1))
                self.assertFalse(worker.submit({}))
                worker.close()  # Does not wait for the simulated slow provider.
                self.assertFalse(finished.is_set())
                self.assertFalse(worker.submit({}))
            finally:
                release.set()
                worker.thread.join(1)
            self.assertIsNone(worker.poll())

    def test_greeting_cadence_visible_snapshot_and_incoming_filter(self):
        with tempfile.TemporaryDirectory() as folder:
            sent = []

            async def send(message, team_only):
                sent.append((message, team_only))

            visible = NS(is_visible=True, type_id=NS(name='MARINE'))
            hidden = NS(is_visible=False, type_id=NS(name='BATTLECRUISER'))
            ai = NS(time=0, options=NS(human_training=True), player_id=2,
                    telemetry=NS(output=folder), state=NS(chat=[]),
                    enemy_units=[visible, hidden], enemy_structures=[], units=[],
                    minerals=50, vespene=0, supply_used=12, supply_cap=15,
                    townhalls=[], chat_send=send)
            worker, wall = FakeWorker(), [0.0]
            rng = NS(uniform=lambda low, high: 90.0)
            runtime = BanterRuntime(ai, worker, rng=rng, clock=lambda: wall[0])
            try:
                asyncio.run(runtime.step())
                self.assertEqual(''.join(value for value, _ in sent), GREETING)
                self.assertTrue(all(not team for _, team in sent))
                self.assertTrue(all(len(value.encode('utf-8')) <= 200 for value, _ in sent))
                self.assertEqual(worker.requests, [])
                self.assertEqual(runtime._next_comment, 90)
                ai.time, wall[0] = 89, 89
                asyncio.run(runtime.step())
                self.assertEqual(worker.requests, [])
                ai.time, wall[0] = 90, 90
                asyncio.run(runtime.step())
                self.assertEqual(len(worker.requests), 1)
                payload = worker.requests[-1]
                self.assertEqual(payload['kind'], 'comment')
                self.assertEqual(payload['battlefield']['enemy_visible'], {'MARINE': 1})
                self.assertNotIn('BATTLECRUISER', json.dumps(payload))
                ai.time, wall[0] = 100, 100
                asyncio.run(runtime.step())  # Busy: no second HTTP request.
                self.assertEqual(len(worker.requests), 1)
                worker.busy, worker.result = False, {'ok': True, 'content': '稳住先别急'}
                ai.time, wall[0] = 101, 101
                asyncio.run(runtime.step())
                before = len(worker.requests)
                ai.state.chat = [NS(player_id=2, message='bot echo'), NS(player_id=1, message='你好')]
                ai.time, wall[0] = 105, 105
                asyncio.run(runtime.step())
                self.assertEqual(len(worker.requests), before)
                ai.time, wall[0] = 116, 116
                asyncio.run(runtime.step())
                self.assertEqual(len(worker.requests), before + 1)
                reply = worker.requests[-1]
                self.assertEqual(reply['kind'], 'reply')
                self.assertEqual([m['text'] for m in reply['human_messages']], ['你好'])
                self.assertEqual(list(runtime._pending_human), [])
                ai.time, wall[0] = 117, 117
                asyncio.run(runtime.step())
                self.assertEqual(list(runtime._pending_human), [])  # SDK overlap was not requeued.
                worker.busy, worker.result = False, {'ok': False, 'error': 'network_timeout'}
                ai.time, wall[0] = 118, 118
                asyncio.run(runtime.step())
                self.assertEqual(len(worker.requests), before + 1)
            finally:
                runtime.close()
            self.assertTrue(worker.closed)

    def test_disabled_and_bad_chat_configuration_do_not_start_or_raise(self):
        ai = NS(options=NS(chat=False))
        with patch('bot.banter_client.Worker') as worker:
            self.assertIsNone(start_banter(ai))
            worker.assert_not_called()
        ai.options.chat = True
        with patch('bot.banter_client.BanterSettings.load', side_effect=ValueError('do-not-print')), \
             patch('builtins.print') as output:
            self.assertIsNone(start_banter(ai))
            self.assertNotIn('do-not-print', repr(output.call_args))

    def test_launcher_switch_is_explicit_and_preserves_decision_identity(self):
        from tools.run_human_training import configuration
        with patch.dict(os.environ, {'SC2_CHAT_ENABLED': '0'}):
            _, disabled = configuration(['--show-config'])
            _, enabled = configuration(['--show-config', '--chat'])
            _, overridden = configuration(['--show-config', '--chat', '--no-chat'])
        self.assertFalse(disabled['chat_enabled'])
        self.assertTrue(enabled['chat_enabled'])
        self.assertFalse(overridden['chat_enabled'])
        self.assertIn('--chat', enabled['game_command'])
        self.assertIn('--no-chat', disabled['game_command'])
        self.assertEqual(enabled['checkpoint'], disabled['checkpoint'])
        self.assertEqual(enabled['actor'], disabled['actor'])
        self.assertNotIn('api_key', json.dumps(enabled).lower())


if __name__ == '__main__':
    unittest.main()
