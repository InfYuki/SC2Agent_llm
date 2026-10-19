"""Opt-in E4 composition of existing asynchronous LLM planning and PPO micro."""
from bot.llm_bot import StrategicBot
from bot.micro_bot import MicroRuleBot


class LLMPPOBot(StrategicBot, MicroRuleBot):
    """Plan -> micro bookkeeping -> one RuleBot macro/combat execution.

    Cooperative super() also initializes one RuleBot/arbiter and closes both
    adapters. StrategicBot supplies economy/army goals; MicroRuleBot owns Marine
    orders, including the shared actor limit, health gate and rule fallback.
    """
