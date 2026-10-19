# P5 heldout终局评估（2026-10-19）

同一冻结heldout配置只运行PPO与原规则kite各1局，两个局部场景均真实击杀Zergling；PPO结束己6HP，规则己1HP。此前20%保护截断没有证明死亡，本轮确认它们在此配置下可继续至击杀。单pair不能证明PPO优于规则、胜率、泛化或课程训练收益；没有追加训练或游戏。

## 评估边界与冻结

仅`tools/run_micro_scenario.py --allow-low-health-eval`允许本地受控场景绕过场景20%退出与微操20%接管门禁。生产`MicroRuleBot.terminal_evaluation()`默认false，默认规则/BC/PPO部署保护保留；支持域、mask、仲裁和命令反馈仍保留，评估PPO加载/推理异常会显式失败。规则`expert()`未修改。评估强制test、非专家且BC不合格，不支持amove/BC替代。

运行前冻结`artifacts/terminal_eval_plan.json`，SHA256 `a0bfb7c3b7fbc11c07ac078b43a5ed7de69bf936ea2e49d4e5be1e362b6ccfea`。包含精确命令、提交faac0c6及未提交评估源SHA、map/lock/run_ppo/model/checkpoint SHA；两局后全部冻结hash不变。checkpoint SHA `9c94690a2cb8eaabfb5fd24c6c0984896825d6f27f87700335f9e41df3aaafd1`、actor weights SHA `8a0e810b5e686fd71fa74f4a7f7b5be486401647b3119b4ec7bd87e1a94bbfc1`。默认`run_ppo.cmd`仍64步actor；无安装、外部模型、.env或奖励变动。

两局相同：Ancient Cistern LE，marine-vs-zergling，名义距离7，己HP .8/36、敌1/35，单敌，max12秒、seed20261019、非实时、8loops。PPO→rule串行，各恰1episode，不换seed/延长时限/重跑；精确命令在[共享证据](validation/ppo_terminal_eval.json)的plan.commands。runtime Python `C:/Users/27932/anaconda3/envs/sc2-ares-runtime/python.exe -s`。公共参数：

```text
tools/run_micro_scenario.py --scenario marine-vs-zergling --distance 7 --health-fraction 0.8 --enemy-health-fraction 1 --enemy-count 1 --max-game-seconds 12 --seed 20261019 --allow-low-health-eval --data-split test --expert kite
```

PPO加`--policy ppo --ppo-model artifacts/models/marine_ppo_curriculum256_20261019 --run-id p5_terminal_eval_ppo_20261019`；规则加`--policy rule --run-id p5_terminal_eval_rule_20261019`。

## 初态、低HP接管与真实终局

两局初始可观测态完全相同：frame17、Marine(82,80)、Zergling(87.892578125,80)，真实距离5.892578125，HP36/35，cooldown0，完整obs/mask与敌角色/in_range相同。名义距离7不等ready距离。源hash相同，但完整引擎随机状态未固定；相同seed与可观测初态不构成严格因果强度对照，后续cooldown/回血细差仍存在。

|策略|决策/请求动作0..4|命令结果|局部终局|己/敌末HP|
|---|---|---|---|---|
|PPO256|15 / [0,4,3,1,7]|7 engine_confirmed、7 hold、1 order_preserved|frame137 / 6.116071429秒 enemy_dead|6 / 0|
|原规则kite|16 / [0,3,3,1,9]|7 engine_confirmed、9 hold|frame145 / 6.473214286秒 enemy_dead|1 / 0|

PPO15次真实inference、15owned，与15条转移一一对应，无fallback。frame129己6HP时仍由PPO选择并执行HOLD4（mask仅HOLD有效），129→137真实8loops后enemy_dead；不是退回规则补打。规则frame129己6HP与137己1HP时仍各接管一次、HOLD4，137→145击杀。所有对应micro_timing controlled=1。低HP之后没有新增非HOLD命令，HOLD保留已有攻击order；hold和order_preserved的confirmed_game_loop=null，不冒充新增引擎命令确认。详细source_obs/mask/requested/executed/confirmation在共享JSON及原始micro_transitions保留。

两局`scenario_result`均terminated=true/truncated=false、enemy_dead_confirmed=true、own_dead_confirmed=false；不是互毁或把缺失敌观测填零。末转移next_obs非None/有效，因为Marine仍存活；敌死亡后next_mask仅HOLD。每条真实8loops、请求/执行mask合法，conflict/非法命令/引擎拒绝/fallback/telemetry error均0，exit0。全部31行test、expert=null、bc_eligible=false，两个run另写learning_exclusion.json及rawSHA永久排除未来训练。原始日志不修改。

场景Recorder仍reward=null/reward_version=not_implemented，**没有训练奖励或可供比较的本轮reward数值**，未凭HP反推写入。完整外层比赛因局部场景结束主动leave，双方官方Defeat/Victory均有日志确认；summary历史status=truncated/stop_reason=game_time_limit只描述外层退出，不能替代局部击杀或宣称全局获胜。两局replay均保存、process exit0，事后Get-CimInstance确认SC2/worker残留0，无Traceback。既有训练预算close EOFError未由本轮修复。

## 范围与后续

实施代理只做1项合并必要定向检查、compile/help/diff，随后仅本pair实机；不重复历史suite。模型/原始证据被Git忽略，迁移需另带。共享完整证据：[ppo_terminal_eval.json](validation/ppo_terminal_eval.json)，原始目录`artifacts/runs/p5_terminal_eval_{ppo,rule}_20261019`，冻结计划与process/log位于artifacts/。本轮建立“受控评估可越过20%并观测真实击杀”的工程事实；生产保护、默认64、旧训练与旧heldout记录保持原样。下一步优先修训练预算关闭协议，再按新授权决定有限任务/初态标准化与小预算比较；P5全面验收、规模就绪与战斗收益仍未建立。
