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
