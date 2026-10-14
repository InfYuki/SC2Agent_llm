from collections import Counter
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch
import asyncio

import run_local
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from bot.arbiter import OrderArbiter
from bot.micro import Action, context, expert, repeated_order
from bot.micro_bot import MicroRuleBot
from bot.micro_data import Recorder
from bot.rule_bot import RuleBot


class Unit:
    def __init__(
        self, tag=1, position=(10, 10), kind=UnitTypeId.MARINE, health=45, cooldown=0
    ):
        self.tag, self.position, self.type_id = tag, Point2(position), kind
        self.health, self.health_max = health, 45
        self.shield = self.shield_max = 0
        self.weapon_cooldown = cooldown
        self.radius, self.ground_range = 0.375, 5.0
        self.real_speed = 3.15
        self.is_visible, self.is_memory, self.is_snapshot = True, False, False
        self.is_flying, self.can_attack_ground = False, True
        self.orders = []

    @property
    def health_percentage(self):
        return self.health / self.health_max

    def distance_to(self, target):
        return self.position.distance_to(getattr(target, "position", target))

    def target_in_range(self, target):
        return (
            self.distance_to(target) <= self.ground_range + self.radius + target.radius
        )


def world(enemies=()):
    return SimpleNamespace(
        enemy_units=enemies,
        structures=[],
        enemy_structures=[],
        in_pathing_grid=lambda point: 0 <= point.x < 100 and 0 <= point.y < 100,
    )


class MicroTests(unittest.TestCase):
    def test_feature_order_counts_and_coordinates(self):
        marine = Unit(health=22.5, cooldown=7.5)
        enemy = Unit(2, (16, 10), health=9)
        friend = Unit(3, (10, 11))
        ctx = context(world([enemy]), marine, [marine, friend], Point2((74, -54)))
        self.assertEqual(len(ctx.obs), 16)
        self.assertEqual(ctx.obs[:4], (0.5, 0.0, 0.5, 0.5))
        self.assertEqual(ctx.obs[12:16], (1 / 16, 1 / 16, 1.0, -1.0))
        self.assertTrue(all(-1 <= value <= 1 for value in ctx.obs))

    def test_no_enemy_and_fog_never_allow_attacks_or_movement(self):
        enemy = Unit(2, (12, 10))
        enemy.is_memory = True
        marine = Unit()
        ctx = context(world([enemy]), marine, [marine], marine.position)
        self.assertEqual(ctx.obs[3:12], (0.0,) * 9)
        self.assertEqual(ctx.mask, (False, False, False, False, True))
        self.assertEqual(expert(marine, ctx), Action.HOLD)

    def test_supported_scope_and_blocked_path(self):
        marine = Unit()
        enemy = Unit(2, (13, 10), kind=UnitTypeId.ZERGLING)
        bot = world([enemy])
        bot.in_pathing_grid = lambda p: p.x >= 10
        ctx = context(bot, marine, [marine], marine.position)
        self.assertFalse(ctx.mask[Action.RETREAT])
        self.assertTrue(ctx.mask[Action.WEAKEST])
        enemy.type_id = UnitTypeId.BANELING
        self.assertFalse(context(bot, marine, [marine], marine.position).supported)

    def test_shoot_weakest_and_kite_during_cooldown(self):
        marine = Unit()
        near, weak = Unit(2, (12, 10)), Unit(3, (14, 10), health=5)
        ctx = context(world([near, weak]), marine, [marine], marine.position)
        self.assertEqual(ctx.weakest.tag, weak.tag)
        self.assertEqual(expert(marine, ctx), Action.WEAKEST)
        marine.weapon_cooldown = 4
        ctx = context(world([near, weak]), marine, [marine], marine.position)
        self.assertFalse(ctx.mask[Action.WEAKEST])
        self.assertEqual(expert(marine, ctx), Action.RETREAT)

    def test_same_order_is_preserved(self):
        marine, enemy = Unit(), Unit(2)
        marine.orders = [
            SimpleNamespace(
                ability=SimpleNamespace(id=SimpleNamespace(name="ATTACK")), target=2
            )
        ]
        self.assertTrue(repeated_order(marine, Action.NEAREST, enemy))

    def test_neutral_rock_blocks_local_move(self):
        marine = Unit()
        enemy = Unit(2, (13, 10))
        bot = world([enemy])
        rock = Unit(3, (8.5, 10))
        rock.radius = 0.8
        bot.destructables = [rock]
        self.assertFalse(
            context(bot, marine, [marine], marine.position).mask[Action.RETREAT]
        )

    def test_ares_clean_grid_uses_x_y_axes_and_blocks_nonfinite_cells(self):
        import numpy as np

        bot = world([Unit(2, (13, 10))])
        grid = np.ones((30, 20))
        grid[8, 10] = np.inf
        bot.mediator = SimpleNamespace(get_cached_ground_grid=grid)
        marine = Unit()
        ctx = context(bot, marine, [marine], marine.position)
        self.assertFalse(ctx.mask[Action.RETREAT])
        self.assertTrue(ctx.mask[Action.APPROACH])

    def test_expert_does_not_kite_a_faster_outranging_threat(self):
        marine = Unit(cooldown=5)
        stalker = Unit(2, (13, 10), kind=UnitTypeId.STALKER)
        stalker.ground_range, stalker.real_speed = 6, 4.13
        ctx = context(world([stalker]), marine, [marine], marine.position)
        self.assertTrue(ctx.mask[Action.RETREAT])
        self.assertEqual(expert(marine, ctx), Action.HOLD)

    def test_confirmation_frame_alignment_and_episode_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "match"
            output.mkdir()
            recorder = Recorder(output, 42)
            marine, enemy = Unit(), Unit(2, (13, 10))
            ctx = context(world([enemy]), marine, [marine], marine.position)
            recorder.begin(
                1, 8, ctx, Action.NEAREST, Action.NEAREST, "queued", enemy, 3674
            )
            # Old action must not confirm the current command.
            command = SimpleNamespace(
                game_loop=7,
                unit_tags=[1],
                ability_id=23,
                target_unit_tag=2,
                target_world_space_pos=None,
            )
            state = SimpleNamespace(action_errors=[], actions_unit_commands=[command])
            recorder.feedback(state)
            self.assertEqual(recorder.pending[1]["command_result"], "queued")
            command.game_loop = 9
            recorder.feedback(state)
            recorder.finish(1, 16, ctx)
            recorder.begin(1, 16, ctx, Action.HOLD, Action.HOLD, "hold")
            recorder.finish(1, 24, terminated=True, reason="unit_death")
            recorder.begin(1, 32, ctx, Action.HOLD, Action.HOLD, "hold")
            recorder.close(40, "game_time_limit")
            rows = [
                json.loads(line)
                for line in (output / "micro_transitions.jsonl")
                .read_text()
                .splitlines()
            ]
            self.assertTrue(rows[0]["bc_eligible"])
            self.assertEqual(rows[0]["command_result"], "engine_confirmed")
            self.assertEqual(rows[0]["next_game_loop"], rows[1]["game_loop"])
            self.assertTrue(rows[1]["terminated"])
            self.assertIsNone(rows[1]["next_obs"])
            self.assertNotEqual(rows[1]["engagement_id"], rows[2]["engagement_id"])
            self.assertTrue(rows[2]["truncated"])
            self.assertFalse(rows[2]["bc_eligible"])
            self.assertEqual(len({r["split"] for r in rows}), 1)

    def test_rejected_and_unconfirmed_commands_are_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder = Recorder(Path(tmp), 7)
            marine, enemy = Unit(), Unit(2, (13, 10))
            ctx = context(world([enemy]), marine, [marine], marine.position)
            recorder.begin(
                1, 8, ctx, Action.NEAREST, Action.NEAREST, "queued", enemy, 3674
            )
            recorder.feedback(
                SimpleNamespace(
                    action_errors=[SimpleNamespace(unit_tag=1, result=9)],
                    actions_unit_commands=[],
                )
            )
            recorder.finish(1, 16, ctx)
            recorder.begin(
                1, 16, ctx, Action.NEAREST, Action.NEAREST, "queued", enemy, 3674
            )
            recorder.finish(1, 24, ctx)
            recorder.close(24, "match_end")
            rows = [
                json.loads(s)
                for s in (Path(tmp) / "micro_transitions.jsonl")
                .read_text()
                .splitlines()
            ]
            self.assertEqual(
                [r["command_result"] for r in rows],
                ["engine_rejected", "engine_unconfirmed"],
            )
            self.assertTrue(all(not r["bc_eligible"] for r in rows))

    def test_hold_reserves_owner_without_sending_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            bot = object.__new__(MicroRuleBot)
            bot.recorder = Recorder(Path(tmp), 42)
            bot.arbiter = OrderArbiter()
            bot.arbiter.begin_step({1: "micro_rule"})
            bot.telemetry = SimpleNamespace(counts=Counter(), event=Mock())
            marine, enemy = Unit(), Unit(2, (13, 10))
            marine.attack, marine.move = Mock(), Mock()
            ctx = context(world([enemy]), marine, [marine], marine.position)
            with patch("bot.micro_bot.context", return_value=ctx):
                bot._execute_micro(
                    marine, ctx, Action.HOLD, [marine], marine.position, 8
                )
            marine.attack.assert_not_called()
            marine.move.assert_not_called()
            self.assertFalse(bot.arbiter.allow(1, "rule_combat"))
            bot.recorder.close(16, "test")

    def test_external_marine_commands_are_blocked_but_macro_is_allowed(self):
        bot = object.__new__(MicroRuleBot)
        bot._authorized_tag = None
        bot.state = SimpleNamespace(game_loop=8)
        bot.telemetry = SimpleNamespace(counts=Counter(), event=Mock())
        marine = Unit()
        worker = Unit(2, kind=UnitTypeId.SCV)
        with patch.object(RuleBot, "do", return_value=True) as submit:
            self.assertFalse(bot.do(SimpleNamespace(unit=marine)))
            submit.assert_not_called()
            self.assertTrue(bot.do(SimpleNamespace(unit=worker)))
            bot._authorized_tag = 1
            self.assertTrue(bot.do(SimpleNamespace(unit=marine)))
            self.assertEqual(submit.call_count, 2)
        self.assertEqual(bot.telemetry.counts["external_marine_commands_blocked"], 1)

    def test_bulk_ares_orders_filter_marine_tags(self):
        bot = object.__new__(MicroRuleBot)
        bot.units = lambda kind: [Unit(1)]
        bot.telemetry = SimpleNamespace(counts=Counter())
        with patch.object(
            RuleBot, "_give_units_same_order", new_callable=AsyncMock
        ) as send:
            asyncio.run(bot._give_units_same_order("move", {1, 2}, "target"))
            send.assert_awaited_once_with("move", {2}, "target")

    def test_death_between_decisions_has_immediate_terminal_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            bot = object.__new__(MicroRuleBot)
            bot.recorder = Recorder(Path(tmp), 42)
            bot.controlled = {1}
            bot.state = SimpleNamespace(
                game_loop=11, dead_units={1}, action_errors=[], actions_unit_commands=[]
            )
            marine = Unit()
            ctx = context(world([Unit(2, (13, 10))]), marine, [marine], marine.position)
            bot.recorder.begin(1, 8, ctx, Action.HOLD, Action.HOLD, "hold")
            with patch.object(RuleBot, "play_step"):
                bot.play_step(9)
            self.assertFalse(bot.recorder.pending)
            self.assertFalse(bot.controlled)
            bot.recorder.close(11, "test")
            row = json.loads((Path(tmp) / "micro_transitions.jsonl").read_text())
            self.assertTrue(row["terminated"])
            self.assertEqual(row["actual_game_loops"], 3)
            self.assertFalse(row["bc_eligible"])

    def test_scenario_setup_error_is_recorded_before_sdk_can_swallow_it(self):
        from tools.run_micro_scenario import ScenarioBot

        bot = object.__new__(ScenarioBot)
        bot.telemetry = SimpleNamespace(fail=Mock())
        with patch.object(
            ScenarioBot,
            "_setup_scene",
            new_callable=AsyncMock,
            side_effect=RuntimeError("no traversable spawn"),
        ):
            with self.assertRaises(RuntimeError):
                asyncio.run(bot.on_start())
        bot.telemetry.fail.assert_called_once_with("scenario_setup")


if __name__ == "__main__":
    unittest.main()
