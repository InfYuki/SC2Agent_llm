"""First-person prompt and conservative fog-of-war mood cues; no external calls."""
import json
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from bot.banter_client import ADAPTER, BanterSettings, request
from bot.banter_runtime import BanterRuntime


class Unit:
    def __init__(self, name="MARINE", x=0, *, ground=True, air=True, flying=False):
        self.type_id = NS(name=name)
        self.x = x
        self.can_attack_ground, self.can_attack_air = ground, air
        self.is_flying, self.is_worker, self.is_structure = flying, False, False
        self.health = self.health_max = 100
        self.shield = self.shield_max = 0
        self.health_percentage = 1
        self.is_visible = True

    def distance_to(self, other):
        return abs(self.x - other.x)


class FirstPersonChatTests(unittest.TestCase):
    def test_mood_uses_local_visible_force_and_checks_anti_air(self):
        with tempfile.TemporaryDirectory() as folder:
            ai = NS(time=90, telemetry=NS(output=folder), units=[], enemy_units=[],
                    enemy_structures=[], structures=[], townhalls=[], minerals=500,
                    vespene=200, supply_used=40, supply_cap=80,
                    calculate_supply_cost=lambda kind: 6 if kind.name == "BATTLECRUISER" else 1)
            runtime = BanterRuntime(ai, NS(close=lambda: None))
            try:
                ai.units, ai.enemy_units = [Unit() for _ in range(4)], [Unit(x=3)]
                cue = runtime._snapshot()["chat_mood"]
                self.assertEqual(cue["stance"], "advantage")
                self.assertIn("得意", cue["emotion"])
                ai.units, ai.enemy_units = [Unit()], [Unit(x=3) for _ in range(4)]
                cue = runtime._snapshot()["chat_mood"]
                self.assertEqual(cue["stance"], "disadvantage")
                self.assertIn("慌张", cue["emotion"])
                # A large distant army cannot justify boasting at the local fight.
                ai.units += [Unit(x=200) for _ in range(40)]
                self.assertEqual(runtime._snapshot()["chat_mood"]["stance"], "disadvantage")
                # No enemies seen is uncertainty, not proof of an overall lead.
                for enemy in ai.enemy_units:
                    enemy.is_visible = False
                self.assertEqual(runtime._snapshot()["chat_mood"]["stance"], "uncertain")
                ai.units = [Unit("SIEGETANK", ground=True, air=False) for _ in range(10)]
                ai.enemy_units = [Unit("BATTLECRUISER", x=3, flying=True)]
                cue = runtime._snapshot()["chat_mood"]
                self.assertEqual(cue["stance"], "disadvantage")
                self.assertIn("visible_local_air_threat_without_nearby_anti_air", cue["evidence"])
                turret = Unit("MISSILETURRET", x=1, ground=False)
                turret.is_structure = True
                turret.is_ready = False
                ai.structures = [turret]
                self.assertEqual(runtime._snapshot()["chat_mood"]["stance"], "disadvantage")
                turret.is_ready = True
                self.assertEqual(runtime._snapshot()["chat_mood"]["stance"], "uncertain")
                # Missing SDK strength data must stay unknown rather than count as zero.
                ai.structures = []
                ai.units = [Unit()]
                ai.calculate_supply_cost = lambda kind: 0
                self.assertEqual(runtime._snapshot()["chat_mood"]["stance"], "uncertain")
            finally:
                runtime.close()

    def test_request_places_sc2_identity_and_emotion_after_original_card(self):
        persona = "original card: default QQ group voice"
        response = NS(status_code=200, json=lambda: {"choices": [{"message": {"content": "我这波有点顺啊"}}]})
        with patch("bot.banter_client.requests.post") as post:
            post.return_value.__enter__.return_value = response
            payload = {"speaker": {"perspective": "first_person"},
                       "battlefield": {"chat_mood": {"stance": "advantage", "emotion": "得意"}}}
            result = request(BanterSettings("mock-chat-only"), payload, persona)
            self.assertTrue(result["ok"])
            messages = post.call_args.kwargs["json"]["messages"]
            self.assertEqual(messages[0]["content"], persona)
            self.assertEqual(messages[1]["content"], ADAPTER)
            self.assertIn("human is YOUR OPPONENT", messages[1]["content"])
            self.assertIn("advantage: act 得意", messages[1]["content"])
            self.assertIn("disadvantage: act 慌张", messages[1]["content"])
            self.assertIn("proactive in-game taunting/challenging IS allowed", messages[1]["content"])
            self.assertEqual(json.loads(messages[2]["content"]), payload)


if __name__ == "__main__":
    unittest.main()
