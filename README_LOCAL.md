# 本地 Ares + LLM + RL 项目

从官方 Ares 模板建立的新工程，按“稳定规则 → LLM 战略 → RL 微操”的顺序实施。本地游戏、完整对局和研究实验是目标。

P0/P1已通过：两地图×五种子10局完整固定步比赛全部正常获胜，另1局完整实时比赛获胜，实时比例约0.995。当前仅验证内置虫族Medium，未据此推断更强对手表现。本地规则基线：`baseline-rule-v1`；详细证据见 [阶段报告](docs/PHASE_01_REPORT.md)。

## 当前可用入口

双击项目根目录的 `run_rule.cmd`，默认人族 Marine 规则版，对战内置虫族 Medium，Ancient Cistern LE，实时完整比赛，直到正常胜负或手动停止。

```bat
cd /d D:\CODE\sc2-ares-llm-rl
run_rule.cmd
run_rule.cmd --show-config
run_rule.cmd --map "Babylon LE" --seed 11
```

测试需要主动设置时长；限时退出会记录为 truncated，不能视为完整比赛失败：

```bat
run_rule.cmd --max-game-seconds 120 --seed 42
run_rule.cmd --no-realtime --max-game-seconds 300 --seed 42
```

`--no-realtime` 用固定游戏步推进，可比实时更快，是本地回归模式；不改变默认入口。

LLM、BC 和 PPO 尚未启用。本阶段不使用旧项目 API 密钥、不加载嵌入模型。规则版的实际验证范围见阶段报告，不将“规则 Bot 能运行”称为完整混合架构已实现。

## 日志、回放和验证

- 控制台日志：`artifacts/last-run.log`。
- 最近一局：`artifacts/latest_run.json` 中的目录。
- 每局：`manifest.json`、`latest_state.json`、`summary.json`、`events.jsonl`、兼容报告和 `game.SC2Replay`。
- 稳定性批次：`artifacts/suites/latest.json` 指向批次汇总。

```bat
conda activate sc2-ares-runtime
python -s -m pip check
python -s -m unittest discover -s tests -v
python -s tools/evaluate_rule.py
```

最后一条将串行执行两地图 × 五种子的 10 局完整比赛，会启动游戏并花费实际时间，不是快速单测。

## 已实现的规则功能

- Ares Mining 管理 SCV，建造通过 Ares mediator/角色系统执行。
- 自动补人口、补工人、建造兵营和持续生产 Marine。
- 二矿目标与有期限的资源预留，避免持续产兵让扩张一直缺钱。
- Marine 集结、防守、进攻与低兵力回撤；后续再引入学习微操。
- 自定义 Marine 控制出口限制每步重复下令，工人和建筑留给 Ares 宏观管理。
- 游戏技能表补充、扩张任务完成回收、异常与退出类型记录。

这是用于建立基线的最小 Marine 策略，尚无完整混合兵种、科技升级、医疗运输机、空投、复杂侦察反制或 RL。对更强对手的能力需要另外验证。

## 版本和回退

详细环境见 [ENVIRONMENT.md](ENVIRONMENT.md)。原项目 `D:\CODE\Large-Language-Models-play-StarCraftII` 保留，新项目使用独立的 sc2-ares-runtime 环境。

框架诊断模式：

```bat
run_rule.cmd --mode template --max-game-seconds 12 --seed 42
```

该模式没有本项目的规则经济和作战，仅用于检查 Ares 框架，不能替代规则基线。

完整规划位于 `D:\GPT-personal\outputs\SC2_Ares_LLM_RL_本地开发规划.md`。原官方模板 README 保留为上游资料；本地实际操作以本文和阶段报告为准。

## 参考来源

官方模板与 Ares 子模块保留其 MIT 许可。用户指定的 SmoothBrain 源码分析、版本比较和后续参考点见 [docs/SMOOTHBRAIN_REFERENCE.md](docs/SMOOTHBRAIN_REFERENCE.md)。未执行用户提供的 ZIP；借鉴的资源优先级思想在独立实现处标明了来源。
