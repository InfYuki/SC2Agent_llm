# P6 E4 LLM战略 + PPO微操完整局工程MVP（2026-10-19）

组合已在一次必要遥测修复重验中自然返回官方 `Result.Victory`、exit0：6次真实HTTP200请求生成6个有效且实际激活计划，428步LLM经济目标、361步军队目标；240次PPO推理与owned transition一致，其中102条微操命令发生在LLM计划实际激活期间。证明本次完整组合链路成立；不能据一个Easy对手成功样本推强度、训练收益、胜率或正式P6验收。

必须同时保留首次失败：初局273.214游戏秒时非关键遥测 `latest_state.json` 原子替换抛WinError5，exit1，无自然官方结局、无回放。修复仅针对该可选快照的Windows短暂替换锁；随后以同地图/种子/模型/难度/步进/时限必要重验一次，没有第三局或挑选策略结果。总真实逻辑调用10次，未超本轮20次预算。

## 配置、冻结与执行边界

源HEAD `1e40ddf74bdb256ec8fa150d3210483050f8f9ae` 加本轮组合及遥测修复工作树，不能将HEAD误作包含新实现的提交。每次各自保存赛前源码/模型/双地图SHA，均与本次赛后立即快照一致；赛后报告变更不属于该冻结区间。

首次plan：`artifacts/p6_e4_fullmatch_20261019/plan.json`，SHA `4c1e71c4a309fef3422d6009b23e2d1cea832cc437852b8756bb02105152c27d`。重验plan：`artifacts/p6_e4_fullmatch_20261019_snapshotfix/plan.json`，SHA `889b7c7cab9e7a7d61c04d58dbdd66eb7a822d89bcd6e7129e6701d23bce32ea`。raw各在同名 `artifacts/runs/e4_fullmatch_llm_ppo_20261019[_snapshotfix]` 目录，完整console/owned进程记录在对应plan目录。

```powershell
& C:\Users\27932\anaconda3\envs\sc2-ares-runtime\python.exe -s -u tools/run_logged.py --mode llm_ppo --ppo-model artifacts/models/marine_ppo_curriculum256_20261019 --map "Ancient Cistern LE" --opponent Zerg --difficulty Easy --no-realtime --game-step 8 --max-game-seconds 1200 --llm-max-calls 16 --seed 20261019 --run-id e4_fullmatch_llm_ppo_20261019_snapshotfix
```

初次命令只在run-id及 `--llm-max-calls 20` 与上述不同。失败实际已调用4次，因此必要重验显式降至16次，以保持本轮总逻辑预算≤20；重验实际6次，累计4+6=10。不是策略调参，未改模型、提示词、stale门限或安全门。每局owned launcher tree的watchdog均600实际秒，均未触发；游戏上限1200秒未触发。未训练、安装、外部模型开发子代理或改API配置；游戏战略沿用既有私密loader与授权DeepSeek配置，密钥未进入CLI或本报告。`run_llm_ppo.cmd`默认调用上限60，不能与本轮显式20/16混淆。

actor weights SHA `8a0e810b5e686fd71fa74f4a7f7b5be486401647b3119b4ec7bd87e1a94bbfc1`，metadata SHA `7f8c0754a6dc65f5d13bbfac18608e26b48b72ebc5f2215fa2bf0674cc932e07`；仓库/安装地图均SHA `13d075a466de88ba93aa3d9f3e9f3743606bffac1bf1b5e81f42b0c56d4a9c59`。工件和模型Git忽略，迁移另带。

## 首次失败与必要修复

首次有效事实仍保留：4请求/4 HTTP200/4 valid active，231步LLM及经济目标、166步军队目标、190等待回调；110推理=110owned=110真实8loops transition，LLM激活时28个微操命令/7微步。32工人/29Marine峰、2基地、生产31Marine，零命令冲突，但遥测异常使整局失败，不算自然终局或完整局通过。

证据代理在失败前用PowerShell `Get-Content`读过运行中的 `latest_state.json`，时序紧邻异常。Windows reader缺少delete-sharing可能阻止原子替换，观察动作可能干扰实验，但未做控制复现，不能断言因果，更不能归因于LLM/PPO决策质量。保留异常、原始plan、tmp与日志，不覆盖失败run。

修复仅让可选 `latest_state.json` 的winerror5/32最多尝试3次，中间10/20ms短等；仍失败保留旧完整快照并记录 `snapshot_skipped`，清理tmp锁也计数。其它必需JSON及非相关异常仍抛出。合并一次针对组合及mock锁的必要检查与compile/diff，未额外实机复现锁。重验仅查看append console；不再读取运行中latest_state。成功局 `latest_state_lock_retries/skips/cleanup_locks` 均0，说明该局未观测到此锁，不能将其冒充真实锁恢复验证。

## 自然完整局、战略实际采用与异步

重验协议进入 `Status.ended`，引擎记录Victory并保存非空回放，SHA `693e35eb8710da19f3bcc34b8e31c4cfda511075e59142d66229ac4840374bb3`。最后回调370游戏秒，launcher39.858实际秒，回调观测span26.847秒；1037 callbacks，on_step p95 7.903ms、max27.368ms。43工人/56Marine峰、生产60Marine、2基地、快照8兵营；最后日志快照369.643秒，43工人/56Marine/2基地、215矿、107/110补给。Ares终局采矿8020、采气0，确有运营发展；结构快照含未完成结构，不能和完成计数混同。

6请求全部HTTP200/合法schema/active，延迟约0.875..1.235实际秒，等待期间累计251次游戏callback，结束无inflight。实际 `llm_steps=428`、`economy_goal_steps=428`、`combat_goal_steps=361`，不是仅收到或解析计划。计划覆盖rally与后期attack，原始plan内容、request_id及时间见共享JSON。LLM激活期间102个PPO owned命令、34个owned微步、17个Marine tag，frames6000..7816；以事件顺序最新 `strategy_source=llm` 区间核对，不把两个互不重叠的子系统误称同时组合。

请求仍由后台单线程/单inflight执行；没有首计划等待、额外节流或放宽45游戏秒时效。5个已激活计划正常过期，609步回退既有规则战略；未见LLM网络/schema/deadline失败，不将正常过期等同网络错误。非实时约13.8x推进，实际采用时长受墙钟API延迟影响，未来不能保证每局都有同样采用比率。

## 微操、仲裁与清理

762个combat微步，连续761个frame差均8loops；69步有owned、最多4Marine逐个共享单体actor。240次真实PPO推理=240owned=240条transition，涉及25Marine tag/6非空目标tag，全部实际8loops，请求/执行mask合法。动作0..4=`[0,13,150,6,71]`，159 engine_confirmed、71 HOLD、3 order_preserved、7 engine_unconfirmed。后3类均不冒充新增引擎确认；未见engine/local/arbiter rejected。局部71条truncated是释放/战略retreat，不是整场截断。

零命令冲突、模型load/inference fallback、策略异常和console Traceback/EOFError/ERROR。生产20%低HP、支持域/静态防御/敌数/控数、战略及释放冷却保护保留；未被PPO拥有单位由规则执行，不等同模型失败fallback。未逐保护原因记录计数，也没逐目标保存真实敌type分布；不能因为Zerg对手就假定推理只见课程Zergling。群体仍是最多4名Marine共享单体actor，并非学成的群体策略。

两局赛后进程快照分别仅保留记录wrapper自身Python，与赛前相同，owned launcher及SC2均无残留；未使用watchdog/强杀取得结果。重验回放与自然Result有效，首次失败没有它们，不能混写“所有日志零错误”。

两run共350条仍是旧Recorder `split=train` 字符串，但全部 `expert=null`、`bc_eligible=false`，未导出或进入任何训练。每个run均保存按raw SHA的 `learning_exclusion.json`，永久排除未来BC/PPO数据收集；reward依旧null/not_implemented，不造训练奖励。共享[e4_fullmatch_mvp.json](validation/e4_fullmatch_mvp.json)同时嵌入失败与重验证据及原始文件SHA。历史训练budgetclose EOFError未由本次修复解决；后续正式P6与效果比较需另行授权预算。
