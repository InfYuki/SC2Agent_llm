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

P2 已加入影子和 LLM 战略入口，见 [LLM 阶段报告](docs/PHASE_02_REPORT.md)。P4 已提供显式启用的 NumPy BC 原型，PPO已有独立最小训练入口；操作见下方P4/P5入口。所有模式均不加载嵌入模型。默认 `run_rule.cmd` 仍独立运行规则，不读取密钥或调用 API。

首轮工程验证通过：120秒影子测试＋同配置规则/LLM各一局完整实时比赛，后两局均获胜；LLM局31次合法计划，实时比例0.994。本次LLM结束更晚，尚无战略收益结论；研究基线 `baseline-llm-v1`。

```bat
run_shadow.cmd
run_llm.cmd
run_llm.cmd --llm-max-calls 10 --seed 42
```

两个新入口同样默认完整实时比赛。影子模式只记录计划；LLM 模式允许模型调整工人/基地目标和主力集结、进攻、防守、撤退任务。遭袭时本地立即防守，网络失败保留尚有效计划，45 秒过期后回到规则。单局最多60次请求，可用 `--llm-max-calls` 减少；设0可验证全程规则回退。

P2 原机验证使用被 Git 忽略的 `.env.local`。新机需复制 `.env.example` 为 `.env.local` 并填写自己的密钥，或设置对应环境变量。模型为 `deepseek-flash`。仅在 LLM/影子入口使用网络，规则和 P3 采集不需要密钥。

## 2026-10-14 新机与 P3 入口

本机项目目录：`C:\code\SC2Agent_llm`；运行环境：`sc2-ares-runtime`（Python3.11.17）。游戏默认目录为 `C:\Program Files (x86)\StarCraft II`；`SC2PATH` 和显式 `--game-path` 可覆盖。两张项目地图已安装。

`run_micro.cmd` 是独立的 P3 规则专家采集入口，保持固定规则战略，最多接管4个 Marine；该入口仍使用规则专家。BC 使用下方独立入口。特征、动作、支持范围和数据标签见 [MICRO_CONTRACT.md](docs/MICRO_CONTRACT.md)，验证与后续事项见 [P3报告](docs/PHASE_03_REPORT.md)。

```bat
cd /d C:\code\SC2Agent_llm
run_rule.cmd
run_micro.cmd
run_micro.cmd --micro-max-units 1 --no-realtime --seed 42
run_micro.cmd --show-config
```

关闭采集/局部专家时直接用 `run_rule.cmd`。`run_micro.cmd` 默认完整实时比赛；限时测试仍需显式传 `--max-game-seconds`。数据与汇总位于每局 `artifacts/runs/<run_id>/micro_transitions.jsonl`、`micro_summary.json`。使用专用环境运行 `python -s tools/report_micro.py artifacts/runs/<run_id>` 审计时间对齐、标签和 episode 边界。

固定1v1诊断入口（固定8游戏帧、禁用宏观、无LLM）：

```bat
conda activate sc2-ares-runtime
python -s tools/run_micro_scenario.py --scenario marine-vs-zergling --seed 42
python -s tools/run_micro_scenario.py --scenario marine-vs-marine --seed 42
python -s tools/run_micro_scenario.py --scenario marine-vs-zergling --realtime --seed 42
```

每次命令独立启动一个有45游戏秒上限的场景。阵容/位置保存在 `scenario.json`，局部结果在 `scenario_result.json`；完整SC2比赛主动截断，不把其 Defeat 当局部失败。该入口没有 Gym reset/step 或 PPO 训练桥接。

后续场景覆盖与A-move对照可使用 `python -s tools/evaluate_micro.py`；数据冻结使用 `tools/export_micro_dataset.py`。场景可加 `--expert amove`、`--distance 3`、`--health-fraction 0.5` 或 `--enemy-hidden`（潜地Zergling诊断）。最新配置恢复与验证见 [P3后续报告](docs/P3_COVERAGE_REPORT.md)。本机DeepSeek配置已安全保存，迁移到其他机器仍需配置自己的凭据。

## 日志、回放和验证

- 控制台日志：`artifacts/last-run.log`。
- 最近一局：`artifacts/latest_run.json` 中的目录。
- 每局：`manifest.json`、`latest_state.json`、`summary.json`、`events.jsonl`、兼容报告和 `game.SC2Replay`。
- 稳定性批次：`artifacts/suites/latest.json` 指向批次汇总。
- LLM 局额外记录：`llm_config.json`、`latest_strategy_snapshot.json`、`strategy_summary.json`，以及 `events.jsonl` 中的请求、延迟、usage、校验结果和实际接管状态。
- 战略成对实验：`artifacts/latest_strategy_pair.json` 指向汇总。

```bat
conda activate sc2-ares-runtime
python -s -m pip check
python -s -m unittest discover -s tests -v
python -s tools/evaluate_rule.py
python -s tools/evaluate_strategy.py --seed 42
```

`evaluate_rule.py` 串行执行两地图 × 五种子的10局完整固定步比赛；`evaluate_strategy.py` 串行执行同地图/种子的规则版、LLM版各一局完整实时比赛，并调用真实 API。两者会启动游戏并花费实际时间，不是快速单测。后一脚本限制自己启动的每局子进程树最多运行1200秒，触发时会记录实验失败；正常游戏入口无整局时长限制。

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
## 2026-10-18 P3双目标与导出状态

suite marine-coverage-v7（场景*-v6）已完成12case×2专家24/24工程检查，导出82条技术合格样本，train32/validation24/test26且每split五动作均出现。58项单测通过。双目标按tag确认血量；双AI场景增加双方官方Result结束屏障。失败v5/v6和pilot均未混入冻结数据。训练就绪仍未建立；P4 已基于此冻结数据完成 BC 工程原型，PPO后续已完成32步工程MVP。最新证据、数据哈希及局部停止遥测限制见 [P3覆盖报告](docs/P3_COVERAGE_REPORT.md)。

单独诊断双目标可在 `tools/run_micro_scenario.py` 使用 `--enemy-count 2 --second-distance 8 --second-enemy-health-fraction 0.5`；实际参数以入口 `--help` 为准。正式冻结和分组审计继续使用 `tools/evaluate_micro.py` / `tools/export_micro_dataset.py`。

## 2026-10-18 P4 BC 快速原型

已训练 NumPy 16→64→64→5（Tanh）模型，显式启用后接管 Marine 局部动作；固定规则战略继续运行。冻结82条样本仅用于工程原型，训练/验证/测试准确率100%/100%/88.46%，不代表战斗收益或泛化。详见 [P4报告](docs/PHASE_04_MVP_REPORT.md)。该BC入口本身不需要Torch/PPO；后续PPO使用独立训练环境。

在本机 PowerShell 使用已有模型：

```powershell
Set-Location C:\code\SC2Agent_llm
conda activate sc2-ares-runtime
$env:PYTHONNOUSERSITE = '1'
$bcModel = '.\artifacts\models\marine_bc_mvp_20261018_seed42'
.\run_bc.cmd --show-config
.\run_bc.cmd
# 独立场景诊断（会启动游戏）
python -s tools/run_micro_scenario.py --scenario marine-vs-marine --policy bc --bc-model $bcModel --seed 42
```

双击 `run_bc.cmd` 或运行 `.\run_bc.cmd` 即加载本次模型，路径以脚本所在目录定位；可用 `--bc-model <其他目录>` 覆盖，默认模型缺失仍回退规则。`run_bc.cmd` 等价于 `run_local.py --mode rule_bc --bc-model <默认模型目录>` 的日志包装入口。默认规则入口仍为 `run_rule.cmd`。模型目录需同时包含 `weights.npz`、`metadata.json` 和 `training_report.json`；运行加载校验契约、权重形状与哈希，加载或推理失败转规则，事件中记录原因。动作使用当帧mask，保留唯一命令出口及低血量保护。BC和其规则回退日志均为 `policy=marine-bc-numpy-v1`、`expert=null`、`bc_eligible=false`，不能混入规则专家训练数据。

模型与冻结原始数据在被Git忽略的 `artifacts/` 中，迁移机器需另行携带；只克隆代码不会取得模型。若已有冻结数据，可在当前NumPy环境重新训练一次（输出目录必须尚不存在）：

```powershell
python -s tools/train_micro_bc.py .\artifacts\micro_datasets\p3_v7_formal_20261018_115352_dataset .\artifacts\models\marine_bc_rebuilt_seed42 --seed 42 --epochs 1000 --learning-rate 0.003
```

训练仅优化train，以validation最小masked loss选权重，最后一次评估test；不要用test调参。82真实行推理一致、两局场景smoke通过；规划1000条真实及边界一致性未做，属于可用MVP而非P4正式验收。

## 2026-10-18 P5 真实环境 MVP

`envs.sc2_micro_env.SC2MicroEnv` 已支持单Marine固定场景的真实 `reset(seed=42)`、`step(action)`、`action_masks()`、`close()`。每步8loops、16维观测、5动作mask；越界/被mask动作在推进前拒绝。奖励为 `(敌方有效HP损失-己方有效HP损失)/45 + 敌死-己死`。这是自定义Gym风格API，非Gymnasium Env；己方死亡可返回`obs=None`及HOLD-only mask，不能直接接标准PPO采样器。系统失败标记`rollout_discard`，不作战术胜负训练。

```powershell
python -s tools/smoke_micro_env.py --seed 42 --max-game-seconds 8 --game-path 'C:\Program Files (x86)\StarCraft II'
```

命令会新启动一局真实SC2；不读LLM凭据。每次reset冷启动worker，MVP不支持动态scenario/options。报告位于`artifacts/micro_env/<episode_id>/`，游戏证据及`rl_rollout.jsonl`位于其`game/`子目录；训练日志为external action、非专家、BC不合格，不混入P3数据。

仅1局真实验证：14步全部8loops，非法动作拒绝不推进，HP奖励逐条一致，marine_dead正常terminated，双方官方Result及worker/SC2进程清理通过。以上为首轮桥接历史范围；后续Gymnasium与32步PPO结果见下节。详情与首次pre-game失败修复见 [P5报告](docs/PHASE_05_ENV_MVP_REPORT.md)、[共享证据](docs/validation/micro_env_mvp.json)。

## 2026-10-19 P5 Gymnasium 与 PPO 最小训练

标准适配 `envs.gym_sc2_micro_env.GymSC2MicroEnv` 已接通：16维float32观测、Discrete5、bool mask；真死亡为空时给零吸收终态，时间截断保留真实obs；系统失败raise并丢弃，不能混入训练。训练Python位于 `C:\code\sc2-ares-training\Scripts\python.exe`，worker仍用锁定Ares runtime；固定依赖见 [requirements-ppo.txt](requirements-ppo.txt)。

一次真实32步MaskablePPO已完成finite actor更新、checkpoint保存与重载概率/动作完全一致；2局完整marine_dead（14/13步），第三局5步因训练预算结束close；49.562秒，零系统失败/命令冲突/SC2残留。seed42起始，随机初始化独立PPO，未用BC权重。模型 `artifacts/micro_ppo/p5_ppo_mvp_20261018/model.zip` 被Git忽略、需另带；本段为首轮32步训练历史范围；最新PPO显式入口见文末续训部署接续，不代表强度提升或P5全面验收。

```powershell
& C:\code\sc2-ares-training\Scripts\python.exe -s tools/train_micro_ppo.py artifacts/micro_ppo/new_run --worker-python C:/Users/27932/anaconda3/envs/sc2-ares-runtime/python.exe --seed 42 --total-timesteps 32 --n-steps 32 --batch-size 16 --n-epochs 2
```

命令启动真实游戏，输出目录必须不存在。证据及边界见 [P5 PPO报告](docs/PHASE_05_PPO_MVP_REPORT.md)、[共享摘要](docs/validation/micro_ppo_mvp.json)。默认规则与BC入口保持原用途，局部训练不读凭据、不调用LLM。


## 2026-10-19 PPO64步续训与部署（历史接续）

已从原32步checkpoint续训新增32步→累计64步，policy与Adam状态保留（optimizer step4→8、updates2→4）；父模型/metadata不变。新checkpoint在`artifacts/micro_ppo/p5_ppo_resume_mvp_20261019/model.zip`，NumPy actor在`artifacts/models/marine_ppo_mvp_20261019`；运行环境无需Torch，独立训练环境负责训练与导出。模型与原始证据不入Git，迁移另带。

双击`run_ppo.cmd`或运行`.\run_ppo.cmd`启动规则宏观+PPO局部Marine；`.\run_ppo.cmd --ppo-model <目录>`覆盖模型。显式mode=rule_ppo；失败记录并转规则，全部PPO/fallback非专家，默认规则/BC用途保留。CLI默认路径已验证，唯一实机部署为单Marine短场景：10次推理/10owned、全部HOLD、4.375秒low_health_safety_exit（己/敌HP均9），无fallback/非法mask/冲突/error/SC2残留。这仅证明链路接管，不证明战斗收益。已有32真实观测SB3/NumPy概率误差5.9604645e-8、动作全同。

继续现64步模型，例新增320步（未运行；继承父n_steps32/batch16/epochs2，输出目录须新建）：

```powershell
& C:\code\sc2-ares-training\Scripts\python.exe -s tools/train_micro_ppo.py artifacts/micro_ppo/p5_ppo_next --worker-python C:/Users/27932/anaconda3/envs/sc2-ares-runtime/python.exe --resume artifacts/micro_ppo/p5_ppo_resume_mvp_20261019 --total-timesteps 320
```

`--total-timesteps`是本次增量、需为32倍数；示例成功后累计384步，恢复optimizer但不承诺完整RNG复演。新训练后按[续训部署报告](docs/PHASE_05_PPO_DEPLOY_MVP_REPORT.md)导出actor，再用`--ppo-model`选新目录。完整事实及边界见该报告和[共享摘要](docs/validation/micro_ppo_deploy_mvp.json)。下一步增加有限训练预算、诊断奖励/动作分布，再少量与规则/BC对比；P5全面验收、规模训练就绪和强度改进均未建立，勿重复旧suite拖延推进。


## 2026-10-19 PPO384步最新接续

已唯一新增320真实步，累计64→384（360.344秒），actor更新、保存重载及320真实观测SB3/NumPy导出一致性通过。新checkpoint：`artifacts/micro_ppo/p5_ppo_train384_20261019/model.zip`；新actor：`artifacts/models/marine_ppo_train384_20261019`。采样21完整marine_dead、另1预算close前5步；完整回报均值-1.498413，未见清晰改善。buffer内系统失败0，但最后budgetclose的worker.log有EOFError且无该局summary/官方Result；训练exit0、异常未入buffer、无SC2残留，关闭边界仍未解决。

训练后仅同新seed20261019串行2探索短场：PPO10HOLD、4.375秒己/敌HP9/9；规则kite5.089286秒HP9/27，均low_health_safety_exit/truncated。初始坐标/HP/frame/mask一致，但武器cooldown不同，不是严格因果对照，不能把HP差归因于策略更强或推出胜率。HOLD保留order可自动攻击；同一320观测父/新actor确定性均HOLD，平均HOLD概率0.309289→0.342991。

`run_ppo.cmd`默认仍是原64步actor，新384步模型是最新而非已证明最佳；显式选择：

```powershell
.\run_ppo.cmd --ppo-model artifacts/models/marine_ppo_train384_20261019
```

模型与原始工件不入Git，迁移另带。完整事实、关闭异常与限制见[PPO384报告](docs/PPO_TRAINING_384_REPORT.md)和[共享摘要](docs/validation/ppo_training_384.json)。下一步诊断预算close、训练任务/奖励及BC初始化，标准化含cooldown的初态后再小对照；本轮不追加游戏或改奖励。P5全面验收、规模训练就绪和强度收益未建立。

### BC actor 初始化PPO最小接续（2026-10-19）

`tools/train_micro_ppo.py --init-bc artifacts/models/marine_bc_mvp_20261018_seed42`可将BC三层actor迁移到新PPO；critic/optimizer新建，与`--resume`互斥。唯一真实新训练32步（累计0→32，非384→416），输出`artifacts/micro_ppo/p5_bc_warmstart_20261019`；训练前82条logits/概率/动作parity成功、BC原hash不变，更新后同82条argmax未变但概率有变化。后续可`--resume`该目录，保留BC来源。

独立actor`artifacts/models/marine_ppo_bc_warmstart_20261019`已导出并保留BC来源。显式运行`.\run_ppo.cmd --ppo-model artifacts/models/marine_ppo_bc_warmstart_20261019`；默认仍原64步模型，旧384步模型保留。唯一部署12决策actions0..4=`[0,3,4,3,2]`，5.044643秒lowHP退出、己/敌9/21；呈现BC式多动作，未做严格对照、不推强度或32步训练收益。budget-close的第三自动reset空局仍EOFError，未入buffer且无SC2残留。详见[BC warm-start报告](docs/PHASE_05_BC_WARMSTART_MVP_REPORT.md)与[共享摘要](docs/validation/ppo_bc_warmstart_mvp.json)。下一步优先近战/射程差可学习任务与小对照，不盲目增加镜像Marine步数；关闭协议与cooldown标准化待办。

## 2026-10-19 近战任务BC初始化PPO128步

已把scenario/distance/时间上限贯穿训练链路，唯一新BC初始化训练0→128（非Marine checkpoint换任务resume）：marine-vs-zergling、名义距6/满HP1v1/12秒/8loops/scale45；真实敌type105/35HP/range0.10009765625，奖励按真实HP差含自然回血。169.688秒、9完整enemy_dead（己10或15HP）+末局3步budgetclose；finite actor更新、reload误差0、128真实obs SB3/NumPy parity动作全同。关闭末局仍EOFError/Traceback，无summary/官方结局、未形成buffer故障，结束无SC2/worker残留。

checkpoint `artifacts/micro_ppo/p5_melee_bc128_20261019/model.zip`；NumPy actor `artifacts/models/marine_ppo_melee_bc128_20261019`，producer保留BC和近战task。显式`.\run_ppo.cmd --ppo-model artifacts/models/marine_ppo_melee_bc128_20261019`选用；默认仍原64步actor，工件Git忽略需另带。继续本近战checkpoint用`--resume`继承task，冲突覆盖拒绝。

仅2局同seed20261019探索：PPO/规则均14决策、6.116071秒enemy_dead、己10HP，动作分别[0,2,2,0,10]/[0,3,2,0,9]。初ready距3.134765625（出生名义距6），cooldown .52783203125/.417236328125不同，无严格对照；同128训练obs原BC/新actor argmax零变化，不推训练收益或胜率。详见[近战报告](docs/PHASE_05_MELEE_PPO_MVP_REPORT.md)与[共享摘要](docs/validation/ppo_melee_mvp.json)。下一步budgetclose、初态标准化及有限独立比较；P5全面验收/规模就绪未建立。

## 2026-10-19 三任务课程续训至PPO256

最新唯一续训从BC来源近战128保留actor/Adam→累计256（新增128、154.375秒），预冻结课程按reset轮转：Zergling距6/满HP→距8/满HP→距8/己HP.6，均敌满HP/12秒/8loops/scale45。显式`--curriculum configs/micro_curriculum_v1.json --allow-task-change`记录父/新任务集；实际A41/B44/C43步，Adam16→32/updates8→16，父文件不变。8完整局6 enemy_dead+2 marine_dead，末C14步budgetclose仍EOFError/Traceback、无summary/官方结果；未入异常transition、无残留。128已有真实观测导出parity概率误差5.66244e-7、动作全同；同观测父/新3个argmax改变，仅证明更新。

新checkpoint：`artifacts/micro_ppo/p5_curriculum256_20261019/model.zip`；actor：`artifacts/models/marine_ppo_curriculum256_20261019`。`run_ppo.cmd`默认仍原64步，显式选择：

```powershell
.\run_ppo.cmd --ppo-model artifacts/models/marine_ppo_curriculum256_20261019
```

仅2场预冻结未训练名义配置距7/己.8/敌1/seed20261019/12秒探索，PPO与规则各13决策、动作均[0,3,3,1,6]，均5.401785714秒low_health_safety_exit、己6HP，敌约.606445/.589355HP；可观测初态含CD0完全一致，但仅1pair不推强度/收益/泛化。安全截断不是死亡/失败；训练与部署保护边界不同。规则raw split=train且12行eligibletrue为旧默认，未进入学习；两run的learning_exclusion sidecar及共享JSON按raw SHA永久排除未来训练。后续探索应显式`--data-split test`，本轮未改raw或重跑。

续训256目录继承内嵌课程，勿再次initBC；任务变化需allow-task-change。模型/证据Git忽略需另带，报告[课程MVP](docs/PHASE_05_CURRICULUM_MVP_REPORT.md)、[共享摘要](docs/validation/ppo_curriculum_mvp.json)。下一步预算关闭协议/训练部署安全边界，再新授权小预算比较；本轮不追加游戏/训练，P5全面验收/规模就绪/收益未建立。


## 2026-10-19 heldout完整终局评估接续

本轮未训练，NumPy curriculum256与原规则kite在同heldout Zergling距7/己.8/敌1/time12/seed20261019串行仅各1局。新增仅本地场景`--allow-low-health-eval`同时绕过场景20%退出和微操20%门禁，仍保留支持域/mask/仲裁，强制test+非专家，PPO加载/推理异常显式失败；生产默认保护与默认64actor不改。执行前plan SHA `a0bfb7c3b7fbc11c07ac078b43a5ed7de69bf936ea2e49d4e5be1e362b6ccfea`，模型/源/map等hash前后不变。

两局初frame17/HP36vs35/实际距5.892578125/CD0/完整obs与mask一致，仍未固定完整引擎状态。PPO15infer/15owned、请求[0,4,3,1,7]，frame137/6.116071429秒enemy_dead、己6HP；规则16owned/请求[0,3,3,1,9]，frame145/6.473214286秒enemy_dead、己1HP。均enemy_dead_confirmed真/own_dead假、terminated真/truncated假。低HP source6HP的PPO仍选HOLD，规则6HP和1HP仍HOLD，全部controlled=1；HOLD延续已有攻击，不冒充新增命令确认。PPO7engineconfirmed+7hold+1preserved，规则7confirmed+9hold，无fallback/conflict/error/残留，exit0。31条均test/expert=null/bc_eligible=false，各run sidecar按rawSHA永久排除训练。

外层主动leave的官方Defeat/Victory与旧summary truncated标签不能替代局部真实击杀；raw reward仍null/not_implemented，未造训练奖励。只1pair不推强度、胜率、泛化或训练收益，不以PPO剩HP/结束时间差排名；此前低HP截断并非死亡，本轮仅证明这次继续至击杀。详见[终局报告](docs/PHASE_05_TERMINAL_EVAL_REPORT.md)、[共享证据](docs/validation/ppo_terminal_eval.json)。模型/原始工件Git忽略需另带；budgetclose EOFError仍待修复，下一步新授权有限比较前先关闭协议/初态标准化；P5全面验收/规模就绪/收益未建立。


## 2026-10-19 E3完整局最新接续

唯一预冻结完整Rule+PPO局已自然官方Victory，exit0：Ancient Cistern LE、Zerg Easy Macro、非实时8loops、seed20261019，1200游戏秒/600墙秒上限均未触发。371.786游戏秒、launcher39.716实际秒；45工人/53Marine峰、58累计Marine、2基地/8兵营。233次PPO推理=233owned=233真实8loops transition，27Marine tags；767combatsteps、最多4名Marine逐个共享单体actor。动作0..4=[0,17,144,8,64]，159engine_confirmed+64hold+4preserved+6engine_unconfirmed；后两类不冒充新确认。mask合法、conflict/error/model-fallback均0，SC2自然cleanup无残留。

当前双击 `run_ppo.cmd` 默认使用 `artifacts/models/marine_ppo_curriculum256_20261019`，是本次E3联调实验模型，不表示更强或最佳；原64模型仍保留，可用 `--ppo-model artifacts/models/marine_ppo_mvp_20261019` 显式选择。默认变更发生在本局结束后，仅show-config静态核验，不追加游戏。本局使用显式run_logged命令，赛时source/model/map预冻结；赛后launcher/文档更新不冒充冻结期间变化。

生产低HP/unsupported/静态防御/控数等保护继续规则combat，不等于模型加载/推理失败fallback；没有逐原因遥测，不能推算次数。支持6敌种而课程仅1Marine对1Zergling，未记录实际敌type分布，不能排除课程外支持敌种推理；多Marine共享actor并非训练过群体策略。仅1局Easy工程Victory，无对照/统计，不推PPO收益、强度、胜率或正式P6验收。

run `artifacts/runs/e3_fullmatch_ppo_20261019`，冻结/console/执行证据 `artifacts/p6_e3_fullmatch_20261019`；报告 `docs/PHASE_06_E3_FULLMATCH_MVP_REPORT.md`，共享 `docs/validation/e3_fullmatch_mvp.json`。raw233条虽旧split=train，全部expert=null/bc_eligible=false，另learning_exclusion按SHA永久排除训练；reward仍null，未训练/未调外部模型/未改API配置/未装包/未重跑。模型及原始工件Git忽略，迁移另带；训练budgetclose EOFError历史问题仍未解决。正式P6及收益评估待新授权预算。


## 2026-10-19 E4 LLM战略 + PPO微操完整局接续

`llm_ppo`已组合既有后台LLM目标与curriculum256 PPO微操，共用单RuleBot/arbiter；新双击入口`run_llm_ppo.cmd`（默认realtime/Medium/调用上限60），本次实验显式非实时Easy且收紧预算，不改变`run_ppo.cmd`默认。运行示例：`.\run_llm_ppo.cmd --difficulty Easy --no-realtime --llm-max-calls 16`；实际已完成命令/冻结SHA以报告为准，不应直接重跑覆盖既有run-id。

首次唯一局273.214游戏秒因可选latest_state.json原子替换WinError5崩溃、exit1、无官方结果/回放；4真实HTTP200/4active、231LLM经济步、166军队目标步、110PPO。证据代理局中Get-Content读快照可能触发Windows删除共享锁，但未证实因果，失败日志完整保留。只修可选快照winerror5/32有限重试/skip，其它必需写和异常不吞；必要同配置/seed重验一次，无第三局、无挑策略结果。初cap20已用4，重验cap16实际6，累计10≤20；未改API配置/提示词/模型/时效门或训练。

重验run `e4_fullmatch_llm_ppo_20261019_snapshotfix`自然官方Victory、exit0，370游戏秒/39.858实际秒；6HTTP200/6valid active、428LLM及经济目标步、361军队目标步、251等待callbacks。240PPOinfer=owned=240真8loops，25Marine tags、mask合法；其中102PPO命令/34owned微步/17tags发生于LLM实际激活区间。159engine_confirmed+71hold+3preserved+7unconfirmed，后者不冒充确认。43工人/56Marine峰、生产60、2基地/8兵营快照、采矿8020；零冲突/模型fallback/重验error/残留，replay保存。snapshot锁retry/skip均0，不声称实机复现了锁修复。

两run共350行均expert=null/bc_eligible=false，旧split=train文字由按rawSHA永久learning_exclusion排除训练，reward仍null。保护继续规则、最多4Marine共享单体actor、敌type与逐保护原因未记录；一个Easy成功样本加一个中止局不推强度/胜率/训练收益。训练budgetclose EOFError历史缺口仍在，正式P6未完成。模型/raw Git忽略需另带。完整双attempt、异常/观察干扰边界、plan/source/model/mapSHA与cleanup见 `docs/PHASE_06_E4_FULLMATCH_MVP_REPORT.md`、`docs/validation/e4_fullmatch_mvp.json`。

## 2026-10-19 P6统一E0–E4离线评估矩阵MVP

`tools/report_evaluation_matrix.py` 可读取 `artifacts/runs` 下run-id或已有run目录，输出统一JSON与可选Markdown；只读已有证据，不启动SC2、API或训练。复现本轮所选历史清单（需另带原始artifacts，在仓库根目录运行）：

```powershell
python -s tools/report_evaluation_matrix.py e3_fullmatch_ppo_20261019 e4_fullmatch_llm_ppo_20261019 e4_fullmatch_llm_ppo_20261019_snapshotfix --output docs/validation/p6_evaluation_matrix_mvp.json --markdown docs/PHASE_06_EVALUATION_MATRIX_MVP_REPORT.md
```

本轮3 attempts＝E3完整Victory 1次＋E4 crashed 1次及完整Victory重验1次。失败保留在attempt分母；未知竞赛结果不记负或胜。已知结果2/2与端到端Victory 2/3仅描述这些工件，不是可推广胜率；E4完整1/2，E0–E2在本轮清单missing，比例为null而非0。局部micro释放/截断不能当作整场截断。汇总器仅汇总调用者提供的run，不能自动证明轮次无遗漏，后续必须显式纳入全部attempt。

共享配置缺少game_build，E4另缺LLM模型记录，已有共享源码SHA也有差异；E4原cap20/重验cap16和修复重验不能当作独立同配置样本。报告[矩阵MVP](docs/PHASE_06_EVALUATION_MATRIX_MVP_REPORT.md)与[共享JSON](docs/validation/p6_evaluation_matrix_mvp.json)分别保留可运行证据、失败、缺失项和比较资格；不构成正式P6验收、强度、泛化或训练收益结论。下一明确小步是统一固定配置的小预算runner，冻结配置/全部attempt清单并补齐缺失模式；新游戏/API预算需另行授权，本历史轮次未执行。

## 2026-10-20 P6固定矩阵runner MVP

`tools/run_evaluation_matrix.py` 默认只冻结plan、0游戏；显式 `--execute` 才运行。仓库根目录用锁定runtime创建新批（目录须新建），例如：

```powershell
& C:\Users\27932\anaconda3\envs\sc2-ares-runtime\python.exe -s tools/run_evaluation_matrix.py --modes E0 E2 --llm-max-calls 0 --batch-dir artifacts/evaluation_batches/NEW_BATCH_ID
& C:\Users\27932\anaconda3\envs\sc2-ares-runtime\python.exe -s tools/run_evaluation_matrix.py --resume artifacts/evaluation_batches/NEW_BATCH_ID --execute
```

每选中模式一次、固定E0→E4顺序，pending才运行，失败/unknown/interrupted保留且不自动重试；冻结源码/解释器/模型/安装地图SHA，变化即拒绝。LLM总预算默认0、上限20，E1/E4分配后不转移；选择LLM模式仍沿用其本地私密配置。batch `state.json`保留全部attempt分母，离线report排除碰撞的foreign raw。批次锁+全仓runner执行锁不协调其它启动器，陈旧锁须先确认owner已退出。

唯一真实批 `p6_runner_e0e2_20261020`：Ancient Cistern LE/Zerg Easy/非实时8/seed20261020/控4，1200游戏秒与600墙秒上限。E0、E2各1局自然官方Victory、exit0，353.571/354.286游戏秒、37.328/34.656 runner墙秒；BC248推理/owned，125确认+117hold+2preserved+4unconfirmed，0fallback/冲突/error，2回放。总0LLM请求/0训练，终态resume实测0新增局。全部248条validation/expert=null/bc_eligible=false/reward=null，rawSHA sidecar永久排除训练；模型/旧raw不变。

详见[runner报告](docs/PHASE_06_MATRIX_RUNNER_MVP_REPORT.md)与[共享JSON](docs/validation/p6_matrix_runner_mvp.json)。原始batch/run/model不入Git、迁移另带。仍缺game_build，本批E1/E3/E4 missing；每模式仅一局Easy、不作强度/胜率/训练收益结论，不合并旧轮次为配对证据。正式P6与训练budget-close历史缺口仍未完成。


## 2026-10-20 P6剩余模式最新接续

唯一新batch `p6_runner_e1e3e4_20261020`预冻结E1/E3/E4各1（Ancient Cistern LE/Zerg Easy/非实时8/seed20261020/控4、1200游戏秒/600墙秒），全部自然官方Victory/exit0/回放，365.000/360.357143/395.714286游戏秒，39.391/36.672/40.360 runner墙秒。实际逻辑请求5+6=11≤总20，分配10/0/10不转移；全部HTTP200/valid active。E1采用402经济/316军队目标步，E4采用434/372。全终态唯一resume exit0/0.375秒、0新增局，0冲突/error/模型fallback事件/SC2残留，无重试/训练/外部模型开发代理/凭据读取/live快照读取。

E3/E4同curriculum256 actor，220/203推理=owned=真实8loops，确认134/132、hold78/62、preserved4/1、unconfirmed4/8，不能称423全下发。423条mask合法/expert=null/bc_eligible=false/reward=null，旧split=train由新增rawSHA learning_exclusion永久排除未来训练，raw/模型不改。生产保护与最多4Marine共享单体actor边界保留。

与旧E0/E2公共配置、地图、Ares、Python及两plan全部240源SHA相同，但冻结revision9f896dee→88206e9为不同plan。限定固定5run集合（旧p6_runner_e0e2的E0/E2＋新p6_runner_e1e3e4的E1/E3/E4）可描述5模式各1工程完成，不泛称所有历史5/5；旧E4首次crashed/unknown仍保留原E4报告与原3attempt矩阵，原完整1/2不变。全部5run缺game_build，E1/E4缺LLM模型标识；单seed n1无强度/胜率/泛化/收益结论，正式P6与训练budget-close历史缺口仍未完成。

plan规范化SHA `fa0c21372c9f10c7c24ad2aa9f48cd182c2b45534ee9d82bf9af24388fcdc298`；完整命令、采用/重叠、source/model/map/log/replay SHA、清单/历史边界见[剩余模式报告](docs/PHASE_06_REMAINING_MODES_MVP_REPORT.md)与[共享JSON](docs/validation/p6_remaining_modes_mvp.json)。原始batch/run/model Git忽略、迁移另带。后续先记录build/LLM模型和评估设计，游戏需新授权；本轮只保存文档，未push。


## 2026-10-20 P6身份追溯离线MVP最新接续

仅离线重生成限定固定5run（p6_runner_e0e2_20261020的E0/E2＋p6_runner_e1e3e4_20261020的E1/E3/E4），无新游戏/API/训练。报告工具现消费本局compatibility-report.sc2_base_build，五run均98370；E1/E4消费llm_config白名单provider/model为DeepSeek/deepseek-flash。旧库存缺game_build 5项与llm_model 2项现均0，无冲突；来源value/source保留。此为报告读取范围补齐，旧manifest/raw不补写。

base_build来自当局SC2 ping，只是部分引擎身份，不是完整version/data_version；LLM仅配置身份，requested/response model仍null、远端行为未冻结。规则模式LLM not_applicable。新工具shared_config_complete/cross_mode_config_match为true仅指跟踪字段匹配，formal_comparison_ready=false；两个plan/revision与单seed每模式n1边界保留，不推正式P6、强度/胜率/泛化/收益。来源冲突/配置请求不一致会阻匹配，legacy缺失保留unknown。

辅助矩阵artifacts/p6_identity_trace_20261020/evaluation_matrix.json/.md；完整命令、旧新缺项、来源及前后SHA见[身份追溯报告](docs/PHASE_06_IDENTITY_TRACE_MVP_REPORT.md)与[共享JSON](docs/validation/p6_identity_trace_mvp.json)。固定5run的33指定证据文件及4个旧报告文件SHA全部不变，raw未改；旧E4 crashed/unknown与原E4完整1/2、原3attempt完整2/3仍完整保留，不泛称所有历史5/5。实现仅扩展现有1项合并定向检查且1/1通过，证据仅唯一CLI/hash/JSON/diff，无额外测试/游戏。未读.env/key/完整配置/base_url、未copy任意配置；未commit/push。正式P6及训练budget-close历史缺口仍未完成，原始工件迁移另带。


## 2026-10-20 P5预算 graceful close 最新接续

预算关闭现发送同episode/decision/frame的close，worker主动leave/双方SDK返回后先落summary再ACK，父端还需exit0；失败显式MicroEnvCloseError并仅清理自有树。worker专用Telemetry延后on_end提前finish，训练清理不覆盖原异常。summary为interrupted/training_budget_close/resultnull，官方Defeat/Victory仅leave握手，不计自然胜负，close不造transition/终态奖励。

唯一2真实短case（Zergling距8/满HP/12秒/seed20261020）：reset-close在decision0/frame17、reset+合法action2退却一步后close在decision1/frame25；原始RL/micro均0/1行，实际一步8loops/engine_confirmed/reward0。两次close各2.094秒、summary先于ACK存在、身份匹配/exit0，无EOFError/Traceback/冲突/worker或SC2残留；base_build98370。68源/两map/4历史证据SHA前后一致，两新case rawSHA sidecar排除未来训练。

plan SHA `9cb3779c2e5f9d850b0f7b217c84286453b6760265535d55dbb55752c2af78ed`，新artifact `artifacts/p5_graceful_close_20261020`；完整结果/33文件SHA见[graceful close报告](docs/PHASE_05_GRACEFUL_CLOSE_MVP_REPORT.md)与[共享JSON](docs/validation/p5_graceful_close_mvp.json)。强制清理/超时失败路径仅mock，未真实kill；旧EOF失败证据保留，未训练/更新模型/调用LLM/完整对局/读凭据或live快照/重跑全suite。两case不是P5全面验收或收益证明。原始工件Git忽略，迁移另带。先推基线f2618cc已在origin/MacZhi-P6；本轮本地待提交、未push。

## 2026-10-21 P5关闭修复后续训最新接续

沿curriculum256唯一实际续训新增64步→累计320，trainer exit0/89.078墙秒（上限300），旧课程/nsteps32/batch16/epochs2/seed42继承，actor/critic/Adam恢复、updates16→20、12项Adamstep32→40，finite且actor改变。64条mask合法/实际8loops、系统失败与discard0；4完整训练局3enemy_dead/1marine_dead，末第5局7步预算close。末466fdd…在decision7/frame73正常close返回并worker78396exit0早于pending save，summary interrupted/training_budget_close/resultnull/errornull、不额外造transition。harness观测正常close返回，未独立抓原始ACK包；身份检查由生产close强制。官方leave结果不计自然战斗胜负，自有PID无残留。

首次artifact observer在初始化空close读未初始化episode_id而exit1，0worker/0真实step、无有效checkpoint；失败完整保留。root仅授权修artifact getter并用新observerfix目录，之后唯一实际64step，不声称全轮零错误。新checkpoint `artifacts/micro_ppo/p5_close_resume320_20261021_observerfix` SHA429b53d24e87c5b0f67bce8da7eabdb696451c37d5d9370809096606792b7b6a；新actor `artifacts/models/marine_ppo_close_resume320_20261021_observerfix` weights SHA2b9a7355f8b2251ae4163ffb0e20e2851ca37081fbfd93e17a0b58f3c4a070cc，producer保留BC/dataset/parent/course来源。旧14文件hash不变、两个默认启动器仍curriculum256，未切默认。SB3reload概率误差0；NumPy只核本次已有1条probe、概率误差2.3283064365386963e-10/动作同，非64条或千条验收。

见[续训闭环报告](docs/PHASE_05_CLOSE_RESUME_MVP_REPORT.md)与[共享JSON](docs/validation/p5_close_resume_mvp.json)，原始证据在 `artifacts/micro_ppo/p5_close_resume320_harness_20261021/observerfix_evidence`。模型/raw Git忽略迁移另带；不推强度/胜率/收益或P5/P6全面验收。无新LLM/API/完整Easy局/安装/源码更改/历史suite；旧EOF证据不改，真实失败kill/timeout与千样本验收仍未覆盖。本轮待root最终保存、未push；后续训练/评估需新授权预算。

## 2026-10-21 PPO256 / 续训320 两短场运行对照最新接续

冻结plan SHA `b22bdf7310784e3bd51191062c3f0f2965bc88e0ae5855c4bd12266439bc4108`，两个显式actor串行各1case、无retry：`p5_resume_compare256_20261021` / `p5_resume_compare320_20261021`，exit0，18.469/17.422墙秒，总35.922。相同名义任务Zergling距7/己.8敌1/单敌/12游戏秒/seed20261021/8loops，eval-only低血绕过、test无专家标签。旧seed20261019已比较256与规则，本轮为重复heldout任务新seed工程观察，不是新未见benchmark。

实际初始已记录字段全同frame17/己[82,80]敌[87.892578125,80]/HP36,35/己CD0/obs及mask；完整隐藏引擎态和敌CD未记录固定，不称严格因果对照。两者14推理=14owned=14条合法8loops，终局同为frame129/5.758928571游戏秒enemy_dead，己6敌0、terminated真/truncated假。256请求分布[0,4,3,1,6]，320[0,3,3,1,7]，实际执行均[0,3,3,1,7]；唯一请求差frame113旧1→执行4/order_preserved，新4→执行4/hold，此时输入cooldown/敌HP和mask已不同，不能归因于同输入模型选择或64步收益。旧7confirmed+6hold+1preserved，新7confirmed+7hold；hold/preserved不是新确认命令。各1条己6HP source仍PPO owned/HOLD；fallback/conflict/error词0，无原因级support fallback遥测，不造分原因统计。

28行test/expert=null/bc_eligible=false，raw SHA learning_exclusion永久排除未来训练，reward仍null；终局以scenario_result/末transition为准，外层Defeat/truncated仅主动leave。冻结source/map/model/default SHA前后不变，事后无SC2进程。没有观察到终局收益，不promote320，两默认启动器仍curriculum256；320显式选择 `artifacts/models/marine_ppo_close_resume320_20261021_observerfix`。报告[运行对照](docs/PHASE_05_RESUME_RUNTIME_COMPARE_MVP_REPORT.md)、[精简证据](docs/validation/p5_resume_runtime_compare_mvp.json)引用 `artifacts/runtime_compare320_20261021` 及两raw目录SHA。旧EOF和observer失败保留，P5/P6全面验收/规模就绪/强度收益未建立；未额外训练/LLM/API/完整Easy局/安装/源码配置改动/旧suite，未commit/push。后续扩展需新预算，模型/raw Git忽略迁移另带。

## 2026-10-21 P5 1v2训练任务接口最新接续

既有场景count2参数已贯通task→SC2MicroEnv→worker→Gym课程/trainer恢复，新增显式 `configs/micro_curriculum_two_enemy_v1.json`（旧3单敌任务+1Marine对2Zergling），旧课程/单敌字典兼容，默认仍旧课程/生产curriculum256；16features/5actions/8loops与原奖励不改。任务版本1v2-v1与场景生成器v6语义不同，不声称所有version相同。

唯一真实case reset→3合法步[2,2,0]→close，exit0/16.437墙秒，plan SHA `cff7379132250081a9b6e5a8257a28ba24e93afa0d961048490355260d10807d`，artifact `artifacts/p5_two_enemy_task_20261021`。seed20261021，名义距6/second8、第二敌半HP/12秒；ready frame19两敌实际距4.426758/6.426758，HP35/17.602539合计52.602539，obs16/mask5。初始化移动/回血使实际值异于名义，未严格固定cooldown。3步实际8loops/confirmed，双敌HP总和52.739258→52.875977→47.063965，己45，奖励-0.0030381944/-0.0030381944/0.129155816逐条复核含第二敌回血；两敌未死，不称真实测all_dead终局。

decision3/frame43原closeACK身份匹配且summary先存在、worker71588 exit0，无SC2/worker残留；summary interrupted/training_budget_close/resultnull/errornull，官方leave结果不计自然胜负。80文件SHA前后同，模型/旧raw/默认未改；3条工程raw按micro/rl SHA learning_exclusion永久排除未来训练，micro reward仍null。真实仅bridge，Gym/trainer仅静态/mock；没有实际1v2训练、学会1v2、收益或P5/P6全面验收。见[1v2任务报告](docs/PHASE_05_TWO_ENEMY_TASK_MVP_REPORT.md)与[共享JSON](docs/validation/p5_two_enemy_task_mvp.json)，原始工件Git忽略迁移另带。无重试/额外局/训练/LLM/API/安装/历史suite/凭据或live快照读取；本轮待root最终保存、未push。

## 2026-10-21 P5首次双敌课程PPO训练最新接续

唯一沿320 checkpoint实际新增128步→累计448，显式新课程/allow-task-change，trainer174.5/launcher177.000秒、exit0；seed42/nsteps32/batch16/epochs2/lr.0003继承，actor/critic/Adam恢复、updates20→28、12项Adam40→56，finite且actor改变/reload误差0。task-set SHA d9bd395a…→ab7a8033…，冷reset从index0开始；实际per-task42/30/29/27，首双敌累计365，2局13/14步共27条实际type105双敌样本，两局均marine_dead。128条obs16/mask5/合法8loops，真实HP奖励复算误差0、trace float32误差3.1789e-8，failure/discard/conflict/expert0；9完整5enemy_dead+4marine_dead，不推学会1v2或收益。

第128步done后自动reset第10空episode e11674f6…，0raw预算close summary interrupted/training_budget_close/resultnull/errornull。生产close成功门先于save/reload/最终zip+成功report/exit0支撑正常保存；未新增observer/独立抓ACK时戳。无worker/SC2残留，旧EOF及observer失败保留。

新checkpoint artifacts/micro_ppo/p5_two_enemy448_20261021 SHA c8d9fdd27b7ace32f776e0a476d300ba22d3278b541810ba07a3d59baf4798b2；新actor artifacts/models/marine_ppo_two_enemy448_20261021 weights SHA50f54edc174d6b0296be6aa9f98c86e4342c33357942db82cc7b0b23926a40c3，producer保留BC/dataset/parent/新旧课程来源。父320三hash不变；唯一已有1probe NumPy概率误差2.037268e-10/同action2，非128或千样本验收。默认两入口仍curriculum256，448显式--ppo-model选择，未promote。

详见[首次双敌训练报告](docs/PHASE_05_TWO_ENEMY_TRAIN_MVP_REPORT.md)与[精简JSON](docs/validation/p5_two_enemy_train_mvp.json)，来源HEAD8e9969e；原始training/evidence/model Git忽略迁移另带。无额外游戏/LLM/API/runtime对照/默认切换/源码配置修改/历史suite/凭据读取；未commit/push。仅证明双敌训练覆盖与工程更新闭环，P5/P6全面验收/规模就绪/强度收益未建立，追加训练或评估需新预算。


## 2026-10-21 P6可选PPO敌域门禁MVP

新增显式 `--ppo-enemy-domain-guard`，默认false；从当前NumPy actor的producer.curriculum.tasks（缺curriculum时才取task）白名单解析敌种与exact数量对，非法/未知域整组拒绝，混种或域外回现有规则且不调用actor。门禁在eligible之前，未改动作mask、奖励或权重，也不限制/证明友军协同。已知448允许ZERGLING1/2，默认256仅1；关闭guard保留旧行为。默认两启动器仍curriculum256，guard不会自动打开，448必须显式选模型并传flag。

唯一真实双敌448 guard-on短case `p6_ppo_enemy_guard448_20261021`，test/seed20261021/名义距6+8、第二敌半HP/12游戏秒上限，无low-health绕过；exit0/17.125墙秒（90上限），无retry。12accepted=12推理=12owned=12条合法16obs/5mask/实际8loops；前9双敌后3单敌，4confirmed+7hold+1preserved（后两者非新确认命令），无error/conflict/PPO或micro异常fallback。末PPO source10HP→next5HP，frame121没有新增PPO决定，20%生产HP边界保留。局部frame121/5.4017857秒 `low_health_safety_exit`、truncated，己5HP/余1敌23.2734375HP；未击杀全部，不把外层主动leave Defeat当战斗终局。低血安全出口属于现有支持门，不是敌域拒绝；没有原因级unsupported计数。

plan SHA `65a9e78b1cd1087788757ce9755b81d9b2725f581caf97b0bbd7e8e39e14612f`；source/map/actor/default冻结哈希前后同，无SC2残留。实际初始frame25己45HP/CD.26196289，两敌距3.134765625/5.134765625、HP35/17.602539，初始化运动/回血未标准化。12条raw test/expert=null/bc_eligible=false/reward=null，并按SHA永久learning_exclusion，不当专家或训练数据。旧256双敌/unknown/混种与关闭兼容仅合并mock（同项合并mock初版及收紧后必要重跑共2次均通过，证据writer未重跑），无额外真实负例。

见[敌域门禁报告](docs/PHASE_06_PPO_ENEMY_DOMAIN_GUARD_MVP_REPORT.md)及[共享JSON](docs/validation/p6_ppo_enemy_domain_guard_mvp.json)，原始 `artifacts/p6_ppo_enemy_guard_20261021` 和对应runs目录Git忽略、迁移另带。仅当前metadata声明的有限敌种/数量准入工程证据，不表示已经学会；不证明友军协同、距离/HP泛化、学习收益或P5/P6全面验收；无训练/API/LLM/完整Easy/安装/默认切换/额外测试游戏/凭据或live快照读取。本轮本地提交保存，未push。


## 2026-10-21 P5 当前448离线一致性验收

唯一离线CLI exit0，当前448 checkpoint/actor严格SHA与16/5契约通过；五固定E3/E4真实raw 233+110+240+220+203=1006 source decision行，distinct obs877（obs+mask877），invalid/重复源0，不称1000独立状态。SB3未归一化logits最大误差3.814697265625e-6、同mask概率9.834766387939453e-7，动作1006/1006一致、near-tie(1e-6)0；默认min1000/tol1e-4达标。synthetic8另列通过，logits1.9073486328125e-6/prob2.444721758365631e-9/动作差0，不计真实数。

首次E4 crashed110仅用于失败前合法推理audit，全部五raw SHA learning_exclusion永久排除训练；16冻结文件前后不变。完整逐行来源报告artifacts/p5_ppo_parity_20261021/parity.json SHA `a735b95b9508165a074438c12ca5ba0d094d393da0ed0772a0af420a4a66d19f`，工具最终SHA `12fa4613a84a18279e6536cb45b33bfa455465bac91f7acf6eaee64f899136d0`。见[一致性报告](docs/PHASE_05_PPO_PARITY_MVP_REPORT.md)及[精简JSON](docs/validation/p5_ppo_parity_mvp.json)。仅当前448导出一致性，不自动完成P4 BC千样本或P5/P6全面验收/强度收益；0游戏/训练/API/安装，默认仍256、guard不自动开，模型/raw迁移另带。未commit/push，待root保存。
