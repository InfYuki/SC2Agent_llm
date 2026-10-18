from collections import Counter
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch
import asyncio
import json
from pathlib import Path
import tempfile

import run_local
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from bot.arbiter import OrderArbiter
from tools.run_micro_scenario import ScenarioBot
from bot.micro_bot import MicroRuleBot
from tools.evaluate_micro import CASES, observed_case_check


class Army(list):
    @property
    def first(self):
        return self[0]


class ScenarioTests(unittest.TestCase):
    def test_invisible_enemy_during_health_setup_still_obeys_time_limit(self):
        bot = object.__new__(ScenarioBot)
        bot._health_ready = False
        bot.options = SimpleNamespace(max_game_seconds=1)
        bot.state = SimpleNamespace(game_loop=1000)
        with patch.object(MicroRuleBot, "on_step", new_callable=AsyncMock) as step:
            asyncio.run(bot.on_step(7))
            step.assert_awaited_once_with(7)

    def test_native_amove_uses_arbiter_and_never_fabricates_discrete_labels(self):
        bot = object.__new__(ScenarioBot)
        marine = SimpleNamespace(
            tag=1, health_percentage=1, health=45, position=Point2((10, 10))
        )
        enemy = SimpleNamespace(
            tag=2,
            type_id=UnitTypeId.ZERGLING,
            is_visible=True,
            position=Point2((16, 10)),
        )
        bot.options = SimpleNamespace(expert="amove")
        bot.recorder = Mock()
        bot.units = lambda kind: Army([marine])
        bot.enemy_units = [enemy]
        bot.enemy_kind = UnitTypeId.ZERGLING
        bot._scene_tag = bot._enemy_tag = None
        bot._enemy_tags = {2}
        bot._dead_enemy_tags = set()
        bot._last_combat_frame = -100
        bot.state = SimpleNamespace(game_loop=8, dead_units=set())
        bot.scene_goal = Point2((16, 10))
        bot.arbiter = OrderArbiter()
        bot.telemetry = SimpleNamespace(counts=Counter(), write_json=Mock())
        bot.issue_rule_order = Mock()
        bot.issue_combat_orders = Mock()
        bot.play_step(1)
        bot.issue_rule_order.assert_called_once_with(
            marine, "attack", bot.scene_goal, 8
        )
        bot.issue_combat_orders.assert_not_called()
        bot.recorder.begin.assert_not_called()
        self.assertEqual(bot.arbiter.owners, {1: "rule_combat"})

    def scene(self, enemies, dead=()):
        bot = object.__new__(ScenarioBot)
        bot.recorder = Mock()
        bot.units = lambda kind: Army([])
        bot.enemy_units = [
            SimpleNamespace(tag=tag, type_id=UnitTypeId.MARINE, is_visible=True)
            for tag in enemies
        ]
        bot.enemy_kind = UnitTypeId.MARINE
        bot._scene_tag = 1
        bot._enemy_tags = {2, 3}
        bot._dead_enemy_tags = set()
        bot.state = SimpleNamespace(game_loop=8, dead_units=set(dead))
        bot._finish_scene = Mock()
        return bot

    def test_first_enemy_death_does_not_terminate_and_second_death_does(self):
        bot = self.scene([3], [2])
        bot.play_step(1)
        bot._finish_scene.assert_not_called()
        bot.enemy_units = []
        bot.state.dead_units = {3}
        bot.play_step(2)
        bot._finish_scene.assert_called_once_with("enemy_dead", True)

    def test_one_surviving_enemy_out_of_vision_truncates_even_with_other_visible(self):
        bot = self.scene([2])
        bot.play_step(1)
        bot._finish_scene.assert_called_once_with("enemy_not_visible", False)

    def test_dead_enemy_no_longer_requires_visibility(self):
        bot = self.scene([3], [2])
        bot.play_step(1)
        bot._finish_scene.assert_not_called()

    def test_health_is_written_per_tag_then_confirmed_in_later_observation(self):
        bot = self.scene([])
        own = SimpleNamespace(tag=1, health=45, health_max=45)
        near = SimpleNamespace(
            tag=2,
            type_id=UnitTypeId.MARINE,
            is_visible=True,
            position=Point2((3, 0)),
            health=45,
            health_max=45,
        )
        far = SimpleNamespace(
            tag=3,
            type_id=UnitTypeId.MARINE,
            is_visible=True,
            position=Point2((8, 0)),
            health=45,
            health_max=45,
        )
        bot.units = lambda kind: Army([own])
        bot.enemy_units = [
            far,
            near,
        ]  # Role assignment uses position, not iteration order.
        bot.options = SimpleNamespace(
            max_game_seconds=45,
            enemy_hidden=False,
            enemy_count=2,
            health_fraction=1,
            enemy_health_fraction=1,
            second_enemy_health_fraction=0.5,
        )
        bot._health_ready = bot._health_written = False
        bot._enemy_tags = set()
        bot._enemy_roles = {}
        bot.enemy_spawn_positions = [Point2((3, 0)), Point2((8, 0))]
        bot._scene_stop = False
        bot.client = SimpleNamespace(debug_set_unit_value=AsyncMock())
        bot._record_initial = Mock()
        asyncio.run(bot.on_step(1))
        self.assertFalse(bot._health_ready)
        self.assertEqual(bot._enemy_roles, {2: 0, 3: 1})
        calls = bot.client.debug_set_unit_value.await_args_list
        self.assertEqual(
            [(c.args[0].tag, c.args[2]) for c in calls], [(1, 45), (3, 22.5), (2, 45)]
        )
        bot._record_initial.assert_not_called()
        asyncio.run(bot.on_step(2))
        self.assertFalse(bot._health_ready)
        bot._record_initial.assert_not_called()
        far.health = 22.5
        with patch.object(MicroRuleBot, "on_step", new_callable=AsyncMock) as step:
            asyncio.run(bot.on_step(3))
            step.assert_awaited_once_with(3)
        self.assertTrue(bot._health_ready)
        bot._record_initial.assert_called_once()

    def test_single_enemy_death_preserves_original_outcome(self):
        bot = self.scene([], [2])
        bot._enemy_tags = {2}
        bot.play_step(1)
        bot._finish_scene.assert_called_once_with("enemy_dead", True)

    def test_suite_keeps_original_cases_and_freezes_split_per_case(self):
        self.assertEqual(
            [c["id"] for c in CASES[:8]],
            [
                "zerg_close",
                "zerg_medium",
                "marine_close",
                "marine_hurt",
                "zerg_hurt",
                "marine_medium",
                "unseen",
                "time_limit",
            ],
        )
        self.assertEqual(len({c["id"] for c in CASES}), len(CASES))
        self.assertEqual(
            {c["split"] for c in CASES if c.get("expected_priority") == 0},
            {"train", "validation", "test"},
        )

    def test_observed_geometry_and_confirmed_action_required_for_dual_case(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            initial = dict(
                initialization_confirmed=True,
                nearest_tag=2,
                weakest_tag=3,
                enemies=[
                    dict(tag=2, health=45, in_range=True),
                    dict(tag=3, health=22.5, in_range=False),
                ],
                weapon_cooldown=0,
                mask=[True, False, True, True, True],
                expert_action=0,
            )
            path = directory / "initial_scene_observation.json"
            path.write_text(json.dumps(initial))
            row = dict(
                requested_action=0,
                executed_action=0,
                command_result="engine_confirmed",
                actual_game_loops=8,
                bc_eligible=True,
            )
            data = directory / "micro_transitions.jsonl"
            data.write_text(json.dumps(row))
            case = dict(enemy_count=2, expected_priority=0)
            self.assertTrue(observed_case_check(directory, case, "kite")["passed"])
            row["bc_eligible"] = False
            data.write_text(json.dumps(row))
            self.assertFalse(observed_case_check(directory, case, "kite")["passed"])
            self.assertTrue(observed_case_check(directory, case, "amove")["passed"])
            initial["enemies"][1]["in_range"] = True
            path.write_text(json.dumps(initial))
            self.assertFalse(observed_case_check(directory, case, "amove")["passed"])
            initial.update(mask=[True, True, True, True, True], expert_action=1)
            path.write_text(json.dumps(initial))
            self.assertTrue(
                observed_case_check(
                    directory, dict(enemy_count=2, expected_priority=1), "amove"
                )["passed"]
            )

    def test_timeout_case_requires_initialized_scene_actual_timeout_and_complete_sample(
        self,
    ):
        case = next(c for c in CASES if c["id"] == "time_limit")
        self.assertEqual(case["limit"], 3)
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            initial = directory / "initial_scene_observation.json"
            result = directory / "scenario_result.json"
            transitions = directory / "micro_transitions.jsonl"
            result.write_text(
                json.dumps(
                    dict(
                        outcome="game_time_limit",
                        truncated=True,
                        terminated=False,
                        game_loop=73,
                    )
                )
            )
            transitions.write_text("")
            # The failed frame-17 run must not become valid by allowing empty data.
            self.assertFalse(observed_case_check(directory, case, "kite")["passed"])
            initial.write_text(json.dumps(dict(initialization_confirmed=True)))
            self.assertFalse(observed_case_check(directory, case, "kite")["passed"])
            self.assertTrue(observed_case_check(directory, case, "amove")["passed"])
            transitions.write_text(
                json.dumps(dict(actual_game_loops=8, truncated=True))
            )
            self.assertFalse(observed_case_check(directory, case, "kite")["passed"])
            transitions.write_text(
                json.dumps(dict(actual_game_loops=8, truncated=False))
            )
            self.assertTrue(observed_case_check(directory, case, "kite")["passed"])
            result.write_text(
                json.dumps(
                    dict(
                        outcome="enemy_dead",
                        truncated=False,
                        terminated=True,
                        game_loop=73,
                    )
                )
            )
            self.assertFalse(observed_case_check(directory, case, "kite")["passed"])
            result.write_text(
                json.dumps(
                    dict(
                        outcome="game_time_limit",
                        truncated=True,
                        terminated=False,
                        game_loop=17,
                    )
                )
            )
            self.assertFalse(observed_case_check(directory, case, "kite")["passed"])


if __name__ == "__main__":
    unittest.main()
