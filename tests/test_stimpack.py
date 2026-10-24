from collections import Counter
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import run_local
from sc2.ids.unit_typeid import UnitTypeId as U
from sc2.ids.upgrade_id import UpgradeId
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from bot.arbiter import OrderArbiter
from bot.upgrades import StimController, StimResearch
from bot.llm_client import EXAMPLE
from bot.strategy import parse_plan, PlanError
from ares.behaviors.macro import UpgradeController


class StimTest(unittest.TestCase):
    def test_plan_and_research_pending_and_resource_gate(self):
        value = deepcopy(EXAMPLE)
        value.update(request_id='s')
        plan = parse_plan(json.dumps(value), 's', 1)
        self.assertEqual(plan.research_priority, ('stimpack',))
        value['research_priority'] = []
        no_research = parse_plan(json.dumps(value), 's', 1)
        self.assertNotEqual(plan.intent, no_research.intent)
        value['research_priority'] = ['stimpack', 'stimpack']
        with self.assertRaises(PlanError):
            parse_plan(json.dumps(value), 's', 1)
        research = StimResearch([UpgradeId.STIMPACK], None, prioritize=True)
        bot = SimpleNamespace(pending_or_complete_upgrade=lambda _: False,
                              structures=lambda _: [],
                              structure_present_or_pending=lambda _: False,
                              minerals=49, vespene=25,
                              telemetry=SimpleNamespace(counts=Counter()))
        with patch.object(UpgradeController, 'execute', return_value=True) as parent:
            self.assertTrue(research.execute(bot, {}, None))
            parent.assert_not_called()
            bot.minerals = 50
            self.assertTrue(research.execute(bot, {}, None))
            parent.assert_called_once()
            bot.pending_or_complete_upgrade = lambda _: True
            self.assertFalse(research.execute(bot, {}, None))
            self.assertEqual(parent.call_count, 1)

    def test_safe_stim_and_single_owner_command(self):
        enemy = SimpleNamespace(is_visible=True, can_attack_ground=True, is_flying=False)
        bot = SimpleNamespace(state=SimpleNamespace(upgrades={UpgradeId.STIMPACK}),
            enemy_units=[enemy], enemy_structures=[], arbiter=OrderArbiter(),
            telemetry=SimpleNamespace(counts=Counter(), event=Mock()))
        for kind, hp, ability, buff in (
            (U.MARINE,45,AbilityId.EFFECT_STIM_MARINE,BuffId.STIMPACK),
            (U.MARAUDER,125,AbilityId.EFFECT_STIM_MARAUDER,BuffId.STIMPACKMARAUDER)):
            with self.subTest(kind=kind):
                unit = Mock(tag=7, type_id=kind, health=hp, health_percentage=1., ground_range=5)
                unit.has_buff.return_value=False
                unit.distance_to.return_value=5
                stim = StimController()
                self.assertFalse(stim.ready(bot,unit,'retreat',100))
                unit.health_percentage=.5
                self.assertFalse(stim.ready(bot,unit,'attack',100))
                unit.health_percentage=1.
                unit.has_buff.return_value=True
                self.assertFalse(stim.ready(bot,unit,'attack',100))
                unit.has_buff.return_value=False
                bot.arbiter.begin_step({7:'rule_combat'})
                self.assertTrue(stim.issue(bot,unit,'attack',100,'rule_combat'))
                unit.assert_called_once_with(ability)
                self.assertIn(7,bot.arbiter.issued)
                self.assertFalse(stim.ready(bot,unit,'attack',108))
                bot.state.upgrades.clear()
                self.assertFalse(stim.ready(bot,unit,'attack',200))
                bot.state.upgrades.add(UpgradeId.STIMPACK)

    def test_marine_ppo_ownership_closes_before_stim_health_cost(self):
        from types import MethodType
        from bot.micro_bot import MicroRuleBot
        order = []
        unit = Mock(tag=7, type_id=U.MARINE, health=45, health_percentage=1., ground_range=5)
        unit.has_buff.return_value = False
        unit.distance_to.return_value = 5
        ctx = SimpleNamespace(supported=True, obs=(0.,) * 16, mask=(True,) * 5)
        bot = SimpleNamespace(
            state=SimpleNamespace(upgrades={UpgradeId.STIMPACK}),
            enemy_units=[SimpleNamespace(is_visible=True, can_attack_ground=True, is_flying=False)],
            enemy_structures=[], arbiter=OrderArbiter(), stim=StimController(),
            telemetry=SimpleNamespace(counts=Counter(), event=Mock()), _last_order={},
            _micro_disabled=False, _ppo_requested=False, _ppo_engagement_gate=False,
            _released_at={}, controlled={7}, options=SimpleNamespace(micro_max_units=4),
            recorder=SimpleNamespace(pending={7: object()}, finish=Mock()),
            choose_micro_action=Mock(), _authorized_tag=None)
        bot.recorder.finish.side_effect = lambda *a, **k: order.append('finish')
        actual = object.__new__(MicroRuleBot)
        actual.__dict__.update(vars(bot))
        bot = actual
        def cast(ability):
            self.assertEqual(bot._authorized_tag, 7)
            self.assertEqual(ability, AbilityId.EFFECT_STIM_MARINE)
            order.append('stim')
            return True
        unit.side_effect = cast
        with patch('bot.micro_bot.context', return_value=ctx):
            MicroRuleBot.issue_combat_orders(bot, [unit], 'attack', None, 100)
        self.assertEqual(order, ['finish', 'stim'])
        bot.recorder.finish.assert_called_once_with(
            7, 100, ctx, truncated=True, reason='stim_rule_override')
        bot.choose_micro_action.assert_not_called()
        self.assertEqual(bot.controlled, set())
        self.assertEqual(bot.arbiter.conflicts, 0)
        self.assertEqual(bot._authorized_tag, None)

if __name__ == '__main__':
    unittest.main()
