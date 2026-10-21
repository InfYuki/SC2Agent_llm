# P5 PPO256 / 续训320 最小运行对照（2026-10-21）

仅执行获授权的两个串行短case，各一次、无重试。两者局部终局均为frame129 / 5.758928571428572游戏秒击杀Zergling，己6HP、敌0；没有观察到终局收益，默认仍curriculum256，不自动提升320。旧seed20261019已用同名义heldout任务比较256与规则，本轮改seed20261021比较256/320，属于重复任务的新seed工程观察，不是全新未见benchmark，也不能以n=1推强度、胜率、泛化或新增64步收益。

## 冻结范围与可恢复证据

基准HEAD `8254e82af6fded6e4b973cb3cb86539cad9de247`。计划 `artifacts/runtime_compare320_20261021/plan.json` SHA256 `b22bdf7310784e3bd51191062c3f0f2965bc88e0ae5855c4bd12266439bc4108` 保存精确命令、预算、来源与冻结hash；本轮仅新报告和交接，不改代码、配置、模型、默认入口或旧工件，不训练/调用LLM或API/运行完整Easy局/安装/重跑历史suite。旧EOF与首次observer失败记录保留。未commit/push。

|项目|256|320|
|---|---|---|
|run-id|p5_resume_compare256_20261021|p5_resume_compare320_20261021|
|actor目录（artifacts/models/）|marine_ppo_curriculum256_20261019|marine_ppo_close_resume320_20261021_observerfix|
|weights SHA256|8a0e810b5e686fd71fa74f4a7f7b5be486401647b3119b4ec7bd87e1a94bbfc1|2b9a7355f8b2251ae4163ffb0e20e2851ca37081fbfd93e17a0b58f3c4a070cc|
|来源checkpoint SHA256|9c94690a2cb8eaabfb5fd24c6c0984896825d6f27f87700335f9e41df3aaafd1|429b53d24e87c5b0f67bce8da7eabdb696451c37d5d9370809096606792b7b6a|
|exit / 墙秒|0 / 18.469|0 / 17.422|

总harness墙钟35.922秒，低于180秒总预算及每case60秒上限，均无timeout。两actor均显式`--ppo-model`选定。来源保留BC→近战128→三任务课程256→续训320；冻结dataset SHA `6558232fea2386e1bef792b50e728b7f5e13ff6a47498837538dd4b0f91aee9e`、BC weights SHA `e36cba313c1d8e1731573595b1b975316e1522db3af8d1a4abf4f21e405c2dcf`。完整producer/parent/course/版本在plan与comparison，不展开复制大树。

## 名义任务与实际配对

公共配置为Ancient Cistern LE、单Marine对单可见Zergling，名义距离7、己/敌HP比例.8/1、seed20261021、非实时、每决策8loops、12游戏秒上限，显式`--allow-low-health-eval --data-split test --expert kite --policy ppo`。`expert kite`是场景配置参数；本轮并无专家学习标签。

实际初始化全部已记录可观测字段相同：frame17、己位置[82,80]、敌[87.892578125,80]、实际距离5.892578125、HP36/35、己weapon_cooldown0、完整16维obs、mask、tag、敌角色/in_range。scene配置、公共manifest、map与source hash一致；共享JSON逐字段保留actual配对布尔值和初态。名义出生距离不等ready距离。未记录的敌cooldown及完整引擎隐藏状态未固定/验证，不能称完全固定初态或严格因果对照。

## 决策、低血边界与局部终局

|指标|256|320|
|---|---|---|
|真实推理 / owned / transitions|14 / 14 / 14|14 / 14 / 14|
|requested动作0..4|[0,4,3,1,6]|[0,3,3,1,7]|
|executed动作0..4|[0,3,3,1,7]|[0,3,3,1,7]|
|命令结果|7 engine_confirmed + 6 hold + 1 order_preserved|7 engine_confirmed + 7 hold|
|局部终局|enemy_dead、terminated=true、truncated=false|相同|
|末HP / 死亡确认|己6/敌0；own_dead=false、enemy_dead=true|相同|

唯一请求动作差在frame113：256请求1、实际执行4/order_preserved；320请求4、实际执行4/hold。双方confirmed_game_loop=null，执行动作相同。此时输入已分歧：256 mask=[true,true,false,false,true]、320仅HOLD有效；cooldown与敌HP特征也不同，不能把请求差异解释为同输入下模型选择变化或新增64步的因果效果。HOLD与preserved保留既有order，不等于重新下发并被引擎确认。

每case均有1条低血source观测（己6HP），PPO继续owned并选择HOLD；末转移frame121→129真实8loops确认敌死。所有请求/执行mask合法、全部actual_game_loops=8，model/micro fallback与conflict均0，summary error=null，Traceback/EOFError/Unknown exception词计数均0。没有原因级support fallback遥测，不能据此编造各原因安全计数。

低血绕过仅限本地受控评估的场景20%退出和接管门禁；生产20%保护、支持域、mask与仲裁保留。28条原始转移全test、expert=null、bc_eligible=false，两run的learning_exclusion.json绑定raw SHA永久排除未来BC/PPO训练；raw不修改。奖励仍null/not_implemented，没有本轮训练奖励。外层主动leave的Result.Defeat及通用summary truncated标签不能替代scenario_result与末转移确认的局部击杀，也不代表全局获胜。

## 完整性与接续

冻结source/map/model/default hash执行前后不变，事后SC2进程清单为空。原始目录 `artifacts/runs/p5_resume_compare{256,320}_20261021`，执行/完整性/释放在 `artifacts/runtime_compare320_20261021/{execution.json,integrity.json,RELEASE.md}`。精简[共享JSON](validation/p5_resume_runtime_compare_mvp.json)引用上述证据与各raw SHA；模型和raw被Git忽略，换机另带，latest_state未读取。

本pair关闭“320能否沿同一短场景运行至真实终局”的工程问题，没有建立优于256的证据。两个默认启动器仍curriculum256，320继续显式选择；P5/P6全面验收、规模训练就绪与收益仍未建立。后续训练/游戏/更大比较需另给预算，不因本轮相同终局自动扩跑。
