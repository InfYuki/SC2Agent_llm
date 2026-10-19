# P6 E3 Rule+PPO 完整对局工程 MVP（2026-10-19）

唯一预冻结完整局自然结束：官方 `Result.Victory`、exit0，规则宏观正常扩张造兵，NumPy curriculum256 actor 在真实战斗中233次接管。它证明本次完整宏观与局部策略链路可一起运行；只有1局Easy对手，没有规则对照，不证明PPO提高胜率、战斗收益或泛化。

## 冻结与唯一执行

源码HEAD `0f31a6223b8ca3ede86f6385d3319af608d3569a`。执行前保存 `artifacts/p6_e3_fullmatch_20261019/plan.json`，SHA256 `ee1c3250186ac1421659f7309053f28a056444eb7ddb57be50dc34f177d84788`；包括源码、模型、仓库及安装地图哈希。运行期间源码与模型哈希前后完全相同。原始目录 `artifacts/runs/e3_fullmatch_ppo_20261019`，单独console与owned进程记录在前述plan目录。

```powershell
& C:\Users\27932\anaconda3\envs\sc2-ares-runtime\python.exe -s -u tools/run_logged.py --mode rule_ppo --ppo-model artifacts/models/marine_ppo_curriculum256_20261019 --map "Ancient Cistern LE" --opponent Zerg --difficulty Easy --no-realtime --game-step 8 --max-game-seconds 1200 --llm-max-calls 0 --seed 20261019 --run-id e3_fullmatch_ppo_20261019
```

仅运行上述1局，没有重试、换seed、训练、安装、外部模型调用或eval低血量绕过。artifact wrapper实施600实际秒watchdog，仅允许清理自己的launcher PID树；本次自然退出，watchdog未触发。Easy用于快速工程联调，非原P1 Medium验收复测。引擎日志确认 `Computer Easy(Zerg, Macro)`。

actor weights SHA256 `8a0e810b5e686fd71fa74f4a7f7b5be486401647b3119b4ec7bd87e1a94bbfc1`，metadata SHA256 `7f8c0754a6dc65f5d13bbfac18608e26b48b72ebc5f2215fa2bf0674cc932e07`。本局显式选择课程256。游戏结束后，另将run_ppo.cmd默认切为此次E3联调实验模型，并只做show-config静态核验；它不是更强/最佳模型结论，原64工件保留并可显式覆盖。plan/execution相等是赛时冻结快照，不代表赛后文档与launcher更新后整个仓库仍未变化；本局实际命令没有使用run_ppo.cmd。

## 实际完整局与宏观

官方协议进入Status.ended并返回Victory，回放已保存且非空；没有gamecap/主动leave。最后回调为frame8328/371.785714286游戏秒，完整launcher墙时39.716秒，游戏回调观测span24.843秒。1042次callback；on_step p95 5.556ms、最大22.102ms。

工人峰45、Marine峰53、累计生产58、基地峰2，快照兵营峰8。最后状态45工人/53Marine/2基地、410矿、104/110补给；Ares终局日志记录采矿8110、采气0。上述真实状态与生产计数证明存在完整运营发展，不能把结构完成计数与快照总量混为一谈。

## 实际微操与命令证据

767个combat决策步，连续frame差766/766均8loops；其中70步至少1名Marine被PPO拥有，同步最多4名。233次成功推理=233个owned决策=233条transition，涉及27个Marine tag、7个非空目标tag。全部transition实际间隔8loops，请求/执行mask均合法；动作0..4计数 `[0,17,144,8,64]`。

命令结果159 `engine_confirmed`、64 `hold`、4 `order_preserved`、6 `engine_unconfirmed`。这6条未确认命令保留为未确认，不冒充引擎成功或引擎错误；无 `engine_rejected`、`local_rejected`、`arbiter_rejected`。HOLD与preserved保留已有命令，不是新增攻击确认。233条结束理由179空、50 control_released、4 strategy_retreat，54条局部truncated不代表整场截断。

`command_conflicts=0`，telemetry error为空，console无Traceback/ERROR/EOFError，模型加载/推理fallback均0，模型规则fallback决策0。赛后日志确认SC2正常退出；前后进程快照相同，仅包含记录wrapper自身Python PID60944，launcher PID66900及SC2均无残留。

## 生产保护与证据边界

生产20%低HP退出、unsupported/静态防御/支持敌数上限/控数上限/战略状态/释放冷却均保留，未选中单位继续规则combat。它们与模型加载/推理失败的 `ppo_rule_fallback_decisions` 是不同机制。本次没有逐原因门禁遥测，不能从非owned步或50次control_released倒推出各保护触发次数。

实际代码支持Marine、Zergling、Roach、Hydralisk、Zealot、Stalker六种敌人；训练课程为1 Marine vs 1 Zergling。当前是最多4名Marine分别共享单体actor，并非已训练群体策略。Zerg敌种与课程相同不能保证本局目标都是Zergling；日志未逐目标保留实际type分布，不能排除对课程外支持敌种推理。没有为补齐该字段另开游戏或安装解析工具。

233条仍有旧Recorder自动 `split=train` 字符串，但全部 `expert=null`、`bc_eligible=false`，policy均marine-ppo-numpy-v1；没有导出或进入训练。run内 `learning_exclusion.json` 按raw SHA永久标记 `excluded_from_future_training=true`，未来收集训练须排除。reward仍null/not_implemented，未伪造训练回报。

原始工件/模型未入Git，换机需另带。共享可审计摘要：[e3_fullmatch_mvp.json](validation/e3_fullmatch_mvp.json)，含原始文件与回放SHA、宏观快照、逐步统计和进程证据。只做本次原始记录一致性/mask/8loops/hash/cleanup核验及赛后launcher静态核验，没有重跑历史suite。游戏期间不修改源码；训练预算close EOFError等历史缺口未由本局解决。正式P6验收与统计尚未完成。下一步如要论证效果，需要新授权的预冻结规则对照与多样本，不能用本局Victory替代。
