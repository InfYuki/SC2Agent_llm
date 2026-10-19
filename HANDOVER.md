# SC2Agent_llm 工作交接与换机恢复

交接日期：2026-10-19。仓库：<https://github.com/InfYuki/SC2Agent_llm>。

## 先了解当前做到哪里

目标是在本地完整实时对局中，以 **LLM 做上层战略、Ares 执行宏观与规则作战、后续 RL 接管局部 Marine 微操**。用户不参加 AI Arena，不将其比赛限制或上传流程作为项目要求。

| 阶段 | 实际状态 | 可恢复的版本与证据 |
|---|---|---|
| P0 环境与 SC2 连接 | 已通过 | Ares3.15.0 / Python3.11 / 固定依赖锁 |
| P1 规则基线 | 已通过工程验收 | `baseline-rule-v1`，提交 `5b0c039e888e5a474f1ff1433634ce698c746e15`；两地图×五种子10局固定步完整获胜，另1局完整实时获胜 |
| P2 LLM战略首版 | 已通过工程验收 | `baseline-llm-v1`，提交 `bafd143ed70a8b451a9879e55f02ff9bb36a5c5f`；影子测试及规则/LLM各1局完整实时比赛通过 |
| P2 正式强度比较 | 未完成 | 本轮仅一个成对工程样本，不能宣称 LLM 提高胜率 |
| P3 微操接口与规则专家数据 | 接口、双目标及v7覆盖批次工程验证通过；训练就绪未建立 | 12case×2专家24/24通过，82条冻结技术合格样本，每split五动作均出现；见 `docs/P3_COVERAGE_REPORT.md` |
| P4 BC工程原型 | 已训练并提供显式运行入口 | NumPy 16→64→64→5，冻结82条；见 `docs/PHASE_04_MVP_REPORT.md`，不代表训练就绪或战斗收益 |
| P5真实训练桥接与PPO MVP | Gymnasium适配、32步真实PPO更新及保存重载通过；整阶段未正式验收 | 独立训练环境，2完整+1部分episode；见 `docs/PHASE_05_PPO_MVP_REPORT.md` |

当前默认入口仍是规则版。LLM是单独入口，网络失败不会同步卡住游戏。完整规划已经复制到仓库 [docs/DEVELOPMENT_PLAN.zh-CN.md](docs/DEVELOPMENT_PLAN.zh-CN.md)，无需访问旧电脑 D:\GPT-personal 才能阅读。详细实现及证据见 [P1报告](docs/PHASE_01_REPORT.md)、[P2报告](docs/PHASE_02_REPORT.md)、[本地说明](README_LOCAL.md)。规划中的未实施条目不能当作现成代码。

本次换机准备只调整启动脚本的环境定位、资料/地图和模板工作流；已验证的 Bot 实现保持 P2 基线内容。基线tag指向历史验收版本，包含可移植启动脚本和交接资料的版本在当前 main。

## 新电脑恢复步骤（Windows / PowerShell）

原电脑是Windows。本流程按Windows准备；其他系统的游戏安装、扩展编译和启动方式尚未在本项目验证。当前规则/LLM版不要求CUDA或独显，不需要下载嵌入模型。

### 1. 安装外部软件并克隆

安装 Git、Anaconda或Miniconda，以及可通过官方API启动的《星际争霸II》本体。保留Git和Conda在终端可用。SC2不是pip包，也未随代码上传。

```powershell
New-Item -ItemType Directory -Path D:\CODE -Force | Out-Null
Set-Location D:\CODE
git clone --recurse-submodules https://github.com/InfYuki/SC2Agent_llm.git sc2-ares-llm-rl
Set-Location .\sc2-ares-llm-rl
git submodule update --init --recursive
git submodule status
git tag --list 'baseline-*'
```

项目目录可改到其他盘。`ares-sc2`必须是已初始化的Git子模块，固定在 `70a151a66fdd00d6c1ee44718735d0da396b902e`；空文件夹会导致Ares/sc2_helper导入失败。不要用“Download ZIP”代替递归克隆，也不要直接更新子模块到上游最新版。

### 2. 重建运行环境和独立Poetry工具

在能使用conda的PowerShell中执行；若环境名已存在，先检查并复用，不要覆盖其他项目环境。

```powershell
conda create -n sc2-ares-runtime python=3.11 pip -y
conda activate sc2-ares-runtime
$runtimePrefix = $env:CONDA_PREFIX
$env:PYTHONNOUSERSITE = '1'

New-Item -ItemType Directory -Path .local-setup -Force | Out-Null
& "$runtimePrefix\python.exe" -s -m venv .local-setup/poetry-tool
& ./.local-setup/poetry-tool/Scripts/python.exe -s -m pip install 'poetry==2.2.1'

# 将工具与运行依赖隔离，但让Poetry明确安装到目标Conda环境。
$env:VIRTUAL_ENV = $runtimePrefix
$env:POETRY_VIRTUALENVS_CREATE = 'false'
$env:POETRY_SYSTEM_GIT_CLIENT = 'true'
& ./.local-setup/poetry-tool/Scripts/poetry.exe env info --path
# 上条应输出 $runtimePrefix，确认后继续：
& ./.local-setup/poetry-tool/Scripts/poetry.exe install --no-root --no-interaction --no-ansi
& "$runtimePrefix\python.exe" -s -m pip check
```

保持 `pyproject.toml`、`poetry.lock` 和子模块版本，不执行 `poetry update`。旧环境Python3.11.17，Poetry2.2.1；新电脑允许同主次版本的可用Python3.11补丁版本，但要记录实际版本并重新验证。旧机器实际依赖清单在 [runtime.freeze.txt](docs/validation/runtime.freeze.txt)，用于比对，不应替代锁文件安装（其中可能含机器相关路径）。

锁文件含Git依赖：python-sc2来自 august-k/python-sc2，commit `194cd34b0ac53aa387fda65c0fc3fc3ed7452697`；MapAnalyzer来自spudde123/SC2MapAnalysis，commit `10133de2b39f2adf2644f081cfdd6bf41d945da5`。安装需要能访问GitHub及Python包源。若新系统没有兼容的预编译扩展并出现编译错误，再根据报错安装Microsoft C++ Build Tools或Rust工具链，不要换成不兼容的主线burnysc2来绕过错误。

### 3. 设置游戏路径和地图

```powershell
$env:SC2PATH = 'D:\game\StarCraft II' # 改为新电脑实际安装目录
New-Item -ItemType Directory -Path (Join-Path $env:SC2PATH 'Maps') -Force | Out-Null
Copy-Item -LiteralPath '.\maps\Ancient Cistern LE.SC2Map' -Destination (Join-Path $env:SC2PATH 'Maps')
Copy-Item -LiteralPath '.\maps\Babylon LE.SC2Map' -Destination (Join-Path $env:SC2PATH 'Maps')
Get-FileHash -Algorithm SHA256 '.\maps\Ancient Cistern LE.SC2Map', '.\maps\Babylon LE.SC2Map'
```

校验值见 [maps/SOURCES.md](maps/SOURCES.md)。新机入口默认游戏路径为 `C:\Program Files (x86)\StarCraft II`；路径不同可设置SC2PATH或每次传 `--game-path`。环境变量设置在当前终端生效；关闭终端后需重设，或自行设置持久用户变量。

### 4. 配置DeepSeek（仅LLM/影子需要）

```powershell
Copy-Item .env.example .env.local
notepad .env.local
```

填写自己的API密钥；base为 `https://api.deepseek.com`，model为 `deepseek-flash`。环境变量 `DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_MODEL` 优先于文件。用户已在本机安全配置 `.env.local`，影子及cap20完整实时LLM局通过，见 `docs/P3_COVERAGE_REPORT.md`；凭据不随Git迁移。不要把密钥放入命令行、日志、交接文本或Git提交中。

纯规则模式不需要密钥。当前LLM适配限官方DeepSeek HTTPS端点和deepseek-flash，显式关闭thinking，使用JSON mode；切换提供方或模型需要新验证。

### 5. 验证后运行

```powershell
conda activate sc2-ares-runtime
$env:PYTHONNOUSERSITE = '1'
python -s -m pip check
python -s -m unittest discover -s tests -v
.\run_rule.cmd --show-config
.\run_llm.cmd --show-config

# 短时连通回归；这里主动离开记录为truncated，不计正常负场。
.\run_rule.cmd --max-game-seconds 30 --seed 42

# 完整实时比赛，无游戏时长上限。
.\run_rule.cmd
.\run_shadow.cmd
.\run_llm.cmd
```

后三条应分别运行、等上一局结束后再开下一局。25项单测和依赖检查在旧电脑通过；新电脑仍需要执行本节验证，不能把旧电脑结果当作新机已通过。

启动脚本现按顺序选择：显式 `ARES_ENV` → 已激活的sc2-ares-runtime → 用户目录的Anaconda/Miniconda常见位置。自定义安装位置可先设置 `$env:ARES_ENV = $env:CONDA_PREFIX`，或将它设为新机器环境的完整目录。脚本不再依赖旧用户名27932。环境被其他Python311用户包污染时，保持 `-s` / `PYTHONNOUSERSITE=1`，不要卸载其他项目的包。

关闭游戏或在终端Ctrl+C可停止；日志包装器只处理自己启动的子进程树。更改调用上限：`.\run_llm.cmd --llm-max-calls 10`；设0不发请求，已有本机配置仍需可读取。

## 验证事实与局限

- P1：两地图Ancient Cistern LE/Babylon LE，各5种子，内置Zerg Medium Macro，10局固定步完整获胜；另1局完整实时获胜。只代表此范围。
- P2影子：120秒主动截断，5请求/5合法计划、实际部队仍按规则；API均值1.175秒，实时比例0.99476。
- P2成对：seed42，同地图/对手，规则406.339游戏秒获胜，LLM467.589游戏秒获胜；实时比例0.98991/0.99398，无异常/命令冲突。
- 完整LLM局31/31合法计划，API均值1.163秒、p95 1.406秒，30577 tokens；不是费用估计。等待期间仍有315次游戏回调，经济与主力目标真实接管。
- LLM局结束较慢约15.1%，工人峰31（规则45）、Marine峰76（规则56）；单个样本不证明因果或胜率提升。LLM on_step p95 6.505ms，但有一次约1.065秒长尾，尚未定位子阶段；不能宣称每帧无抖动。
- 当前没有通用全兵种/科技战略、完整损失交换统计、事件提前查询或完整逐目标完成/取消状态机。不要把工程通过等同全部规划完成。

已上传的 `docs/validation/` 是可分享汇总与失败证据。原始 `artifacts/`（回放、逐请求/逐步日志）、安装缓存和运行环境不进入Git。需要逐事件重放研究时，在旧机另行复制 artifacts；不复制也能从源码重新运行并产生新证据。

## 代码导航与必须保留的适配

| 位置 | 职责 / 后续开发约束 |
|---|---|
| `run_local.py` | 官方协议客户端启动、模式选择、默认实时整局、manifest与源码/地图哈希 |
| `bot/probe.py` / `telemetry.py` | Ares生命周期、异常/截断分类、耗时、状态记录 |
| `bot/rule_bot.py` | Ares Mining/宏观、经济与战略钩子、Marine本地下令；默认无LLM依赖 |
| `bot/strategy.py` | 严格strategy-v1契约，45游戏秒TTL、30游戏秒承诺期 |
| `bot/llm_client.py` / `llm_bot.py` | 单后台线程、周期摘要、5..60秒退避、超时与计划接管 |
| `bot/arbiter.py` | 单位每步唯一命令所有者，P3/RL应扩展该出口，不再创建竞争下令路径 |
| `bot/compat.py` | 引擎技能4135等动态技能表补充；不能把未知技能默认为NULL或擅自猜映射 |
| `bot/building_manager.py` | 修复Ares3.15已完成二矿任务未回收而继续派SCV到第三矿；类名必须保持BuildingManager以适配mediator路由 |
| `bot/lifecycle.py` | 处理SDK结束瞬间查询竞态：必须重新读取官方结果确认，不能将任意ProtocolError伪装正常结束 |
| `tools/probe.py` | 独立日志和自己子进程树watchdog，测试时长限制不等于完整比赛 |
| `tools/evaluate_rule.py` / `evaluate_strategy.py` | 固定步10局规则回归 / 完整实时规则与LLM成对工程实验 |
| `tools/report_*.py` | 由原始证据重建汇总，不启动游戏或调用API |

API调度：摘要1游戏秒；查询每15游戏秒且至少5实际秒间隔；最多1请求且无队列、默认60次/局；连接5秒/读取15秒，20实际秒逻辑截止。底层网络线程尚未结束时继续占唯一槽，主循环不join它；过时结果丢弃，有效旧计划可继续，过期转规则。紧急防守优先，不等待模型。

新游戏版本可能再次新增技能或改变协议行为，应保存新 compatibility-report 并在项目适配，不修改site-packages或直接覆盖上游子模块。每次变动保留已接受基线、一次验证一个候选；测试结果区分完整/截断/异常。

## 下一阶段具体交接

新机已按 [开发规划的P3](docs/DEVELOPMENT_PLAN.zh-CN.md) 完成首轮接口、规则专家和采集候选，实际使用 `run_micro.cmd` / `tools/run_micro_scenario.py`，证据见 [P3报告](docs/PHASE_03_REPORT.md)。下面保留P3阶段要求；P4已在冻结小样本上实现快速BC工程原型，当前操作以P4报告与README为准，后续仍需扩大独立覆盖：

1. 固定小范围Marine微操场景，明确受控单位、可见敌方、战斗半径、结束条件和撤退回退。
2. 冻结 `marine-16-v1` 的16维特征及5类动作的语义、归一化、坐标参照、mask和采样时序；手册是起点，不能直接把示例当可用环境。
3. 接入arbiter的唯一命令出口，使规则专家和将来RL互斥控制同一单位；未接管单位继续当前规则。
4. 先采规则专家数据，严格对齐 observation/action/mask/next observation 与游戏帧，记录episode边界、版本和随机种子，避免同一对局跨训练/测试泄漏。
5. 有真实数据与环境验收后，再开展BC；PPO需真实reset/step桥接与训练部署一致的动作掩码。固定规则战略评估微操，再组合LLM；局部训练不调用远端LLM。

PPO已在独立venv `C:\code\sc2-ares-training` 进行最小训练，worker保持锁定Ares runtime；不要把训练栈装进运行环境。已有BC权重在artifacts/models；PPO模型为artifacts/micro_ppo/p5_ppo_mvp_20261018/model.zip，无运行中的训练进程。

用户参考Bot为 [Myrmecoman/sc2_bot](https://github.com/Myrmecoman/sc2_bot)，固定参考commit `895d8b036af0554e8d49cc6be5925abe54da6ba2`；分析见 [SMOOTHBRAIN_REFERENCE.md](docs/SMOOTHBRAIN_REFERENCE.md)。其宏观自管工人，不可把它的宏观控制与本项目Ares Mining直接叠加；不要混用其自带旧Ares和当前子模块。用户SmoothBrain_data.zip是22字节有效空ZIP，没有训练数据。

## 旧机可选单独携带的资料

| 文件/目录 | 是否必须 | 说明 |
|---|---|---|
| 新项目 `.env.local` | LLM需要重新配置 | 不在Git，用安全方式转移或新机重新输入 |
| 新项目 `artifacts/` | 可选 | 回放及详细实验日志；Git内已有关键汇总 |
| `C:\Users\27932\Downloads\Ares-SC2_RL_Micro_Hybrid_Development_Manual.md` | 继续按原手册开发时建议携带 | 原始用户文档未擅自公开到Git；SHA256 `f983a09bca5de2bf0fbb9f3f0fe6bdc9369544db93ec9fafb75a9d93a644bfde` |
| `D:\GPT-personal\agent-persona` 与 `Long_term_independent_memory_bank` | 需要个人agent偏好/跨任务记忆时可选 | 属于独立私人资产，不属于本代码库，未上传 |
| 旧LLM项目与嵌入模型 | 新项目无需 | `Large-Language-Models-play-StarCraftII` 保留作历史参考，新框架不依赖其环境或模型 |

不复制Conda环境文件夹和Git凭据缓存；在新机按锁文件重建。不要公开整个旧工作区、下载目录、人格记忆或私有配置。

## 给新电脑开发助手的接续提示

> 先读HANDOVER.md、README_LOCAL.md、docs/PHASE_04_MVP_REPORT.md和P3_COVERAGE_REPORT。项目在C:\code\SC2Agent_llm，目标是本地Ares＋LLM战略＋Marine微操，不参加AI Arena。用户偏好快速可用MVP、少重复测试；每小步交子代理，主代理协调核对。P1/P2与P3历史证据保留。P4以冻结82条（32/24/26）训练NumPy BC，val选epoch1000，test准确率88.46%；这是标签拟合工程原型，不证明收益或泛化。显式run_bc.cmd --bc-model启用，默认仍规则；失败规则回退，BC日志不充当专家标签。模型和数据不在Git，迁移需另带。PPO已完成真实32步工程MVP（非强度验收），训练就绪仍未建立。先读docs/PHASE_05_PPO_MVP_REPORT.md，独立training Python+runtime worker，最新PPO显式入口见文末续训部署接续。遵守唯一命令出口、非阻塞LLM及凭据保密。

## 2026-10-18 P3接续状态

suite marine-coverage-v7 / 场景*-v6正式批次 `p3_v7_formal_20261018_115352` 24/24通过；冻结82条技术合格样本，train32/validation24/test26，每split五动作均出现。共享摘要在docs/validation/micro_coverage_v7.json和micro_dataset_v7.json。58/58单测、pip check、diff检查、独立源码审查与最终数据/日志验收通过；suite记录17源哈希，当前无变化。双AI结束屏障要求双方原SDK返回有效官方Result后清理；24局日志均有双方官方Result、无连接已关闭错误，0命令冲突。失败v5（0.6秒初始化窗口不足）和v6（双AI退出竞态）保留且不导出；详情见 [P3覆盖报告](docs/P3_COVERAGE_REPORT.md)。

两种专家各9次低血量安全退出、1次敌人死亡、2次时间上限，未发现优势证据。相同双目标几何不同seed不能作为泛化证明。本段为P3历史状态；P4已完成小样本BC原型，训练就绪仍未建立、PPO未开始。场景局部结果优先读scenario_result.outcome和尾transition.end_reason，summary.stop_reason仍有统一写game_time_limit的分类限制，后续连同Telemetry映射修复。

## 2026-10-18 P4接续状态

快速BC原型已训练并接入 `run_bc.cmd`，双击即按脚本目录定位本次模型；`--bc-model <目录>` 可覆盖，默认模型缺失仍规则回退。NumPy MLP、masked交叉熵和Adam；train优化、validation选权重、test最后评估一次。训练/验证/测试准确率100%/100%/88.46%。新增6项必要定向测试（训练2、运行4）与CLI检查通过，本轮不重复全58项或24局suite。最终推理一致性与两局smoke证据见 [P4报告](docs/PHASE_04_MVP_REPORT.md)。

模型本体不提交；换机单独复制模型目录和冻结数据，或按README重训。82真实行推理一致、两局场景smoke通过；1000条真实及边界一致性未做，P4未正式验收。本段保留P4历史接续要求；其后的P5桥接及PPO最小训练见文末最新接续，小样本准确率不证明BC优于规则。


## 2026-10-18 P5真实桥接MVP接续

SC2MicroEnv自定义Gym风格reset/step/action_masks/close已接真实worker；不是Gymnasium Env，死亡可obs=None。唯一真实episode c06761effef34708901c214e7d7c3bd7，seed42/8秒上限，14步全部8loops，frame17→129；action5及masked0拒绝不推进。HP己45→0/敌45→9，逐条复算奖励一致，总-1.2含死亡终局-1；marine_dead/terminated=true/truncated=false。双方官方Defeat/Victory、worker exit0、close无自有SC2残留；0命令冲突，RL日志非专家/BC合格0，不读LLM凭据。

首次pre-game目录冲突失败已保留，worker Telemetry改game子目录后只运行上述1局。2项必要父端契约测试与worker编译/CLI通过；不重跑全suite。以上为首轮桥接历史范围；后续重复reset、预算close及一次吞吐测量已随32步PPO训练覆盖，见文末最新接续。完整报告docs/PHASE_05_ENV_MVP_REPORT.md，共享docs/validation/micro_env_mvp.json；真实奖励消费RL rollout，旧micro_summary.reward字段与通用summary截断分类不作为环境终止依据。训练就绪仍未全面建立。

## 2026-10-19 P5最新接续

Gymnasium适配与MaskablePPO最小训练已过：32真实步、2完整死亡episode（14/13步）及1预算close部分episode（5步），SB3 n_updates2、参数finite且actor变化，保存重载同obs+mask概率误差0。模型SHA256 `80139d368fbb24a0eb1d6262c3e0dc53b3688ed1c94f1b469d107f118608a793`。原始目录artifacts/micro_ppo/p5_ppo_mvp_20261018，模型不入Git；两完整局官方Result确认，全部32条mask/真实HP奖励复核，无systemfailure/conflict/进程残留。训练49.562秒；无额外评估局，不能推出收益/胜率。

训练环境C:\code\sc2-ares-training（Torch2.10.0+cpu/Gymnasium1.2.3/SB3与contrib2.7.1）；worker仍C:\Users\27932\anaconda3\envs\sc2-ares-runtime\python.exe -s；依赖requirements-ppo.txt，锁文件及子模块未改。2项adapter+1项trainer定向测试/pipcheck通过，不重跑旧suite。系统失败在buffer前raise；真实故障/时间截断/敌死仍未实测。本段为首轮历史工程MVP；P5全面验收/长训未做，最新局部部署见下节。后续优先按用户需要接PPO局部部署与短时行为验证，默认规则/BC/LLM入口保持原用途。


## 2026-10-19 PPO续训与部署最新接续

已从原32步checkpoint续训新增32步→累计64步，policy与Adam状态保留（optimizer step4→8、updates2→4）；父模型/metadata不变。新checkpoint在`artifacts/micro_ppo/p5_ppo_resume_mvp_20261019/model.zip`，NumPy actor在`artifacts/models/marine_ppo_mvp_20261019`；运行环境无需Torch，独立训练环境负责训练与导出。模型与原始证据不入Git，迁移另带。

双击`run_ppo.cmd`或运行`.\run_ppo.cmd`启动规则宏观+PPO局部Marine；`.\run_ppo.cmd --ppo-model <目录>`覆盖模型。显式mode=rule_ppo；失败记录并转规则，全部PPO/fallback非专家，默认规则/BC用途保留。CLI默认路径已验证，唯一实机部署为单Marine短场景：10次推理/10owned、全部HOLD、4.375秒low_health_safety_exit（己/敌HP均9），无fallback/非法mask/冲突/error/SC2残留。这仅证明链路接管，不证明战斗收益。已有32真实观测SB3/NumPy概率误差5.9604645e-8、动作全同。

继续现64步模型，例新增320步（未运行；继承父n_steps32/batch16/epochs2，输出目录须新建）：

```powershell
& C:\code\sc2-ares-training\Scripts\python.exe -s tools/train_micro_ppo.py artifacts/micro_ppo/p5_ppo_next --worker-python C:/Users/27932/anaconda3/envs/sc2-ares-runtime/python.exe --resume artifacts/micro_ppo/p5_ppo_resume_mvp_20261019 --total-timesteps 320
```

`--total-timesteps`是本次增量、需为32倍数；示例成功后累计384步，恢复optimizer但不承诺完整RNG复演。新训练后按[续训部署报告](docs/PHASE_05_PPO_DEPLOY_MVP_REPORT.md)导出actor，再用`--ppo-model`选新目录。完整事实及边界见该报告和[共享摘要](docs/validation/micro_ppo_deploy_mvp.json)。下一步增加有限训练预算、诊断奖励/动作分布，再少量与规则/BC对比；P5全面验收、规模训练就绪和强度改进均未建立，勿重复旧suite拖延推进。


## 2026-10-19 PPO384步有限训练最新接续

唯一从64步checkpoint新增320步→累计384，n_updates4→24、Adam step8→48，360.344秒。新checkpoint `artifacts/micro_ppo/p5_ppo_train384_20261019/model.zip`（SHA256 `543c059aec4cd790322d5e7b9d14c03744c34163e78d6c0d64dfebcc91c6a3c2`）；新NumPy actor `artifacts/models/marine_ppo_train384_20261019`；父模型/metadata不变。320真实8loops合法mask、HP奖励复核通过，参数finite/actor改变/reload概率误差0；320真实观测SB3→NumPy概率误差8.9406967e-8、动作全同。未改reward/实现/依赖，不重跑旧suite。

21完整训练局均marine_dead/官方结果及close确认，己HP0、敌HP15..33均22.429，完整回报均值-1.498413；另1局预算close前5步。buffer内system_failure/discard/conflict均0；最后部分局worker.log在close有EOFError/Unknown exception，无summary/官方Result，异常未入buffer，trainer exit0、已清理无SC2残留；不能写所有日志零错误，关闭异常待修复。五个64步奖励块无清晰改善。采样动作0..4=[23,34,71,89,103]；同320观测父/新确定性均HOLD，平均HOLD概率0.309289→0.342991；HOLD可保留自动攻击，不能单凭动作占比判无效。

训练释放后仅同新seed20261019串行2探索短场、非严格因果对照：PPO10HOLD、4.375游戏秒己/敌HP9/9；规则kite12决策（10engine_confirmed+2hold）、5.089286秒HP9/27，均low_health_safety_exit/truncated，exit0、无fallback/冲突/error/残留。源哈希/初始frame18/几何/HP/mask一致，仅武器cooldown不同；pair_initial_state_fully_matched=false、controlled_comparison=false。HP差不能归因于策略更强，不推胜率、泛化或完整比赛结论；未重跑选seed、未额外运行旧策略/BC。

默认run_ppo.cmd仍指原64步actor；384步只是最新非最佳，用`.\run_ppo.cmd --ppo-model artifacts/models/marine_ppo_train384_20261019`显式选择。模型与原始证据不入Git，迁移另带。详见docs/PPO_TRAINING_384_REPORT.md与docs/validation/ppo_training_384.json。下一步诊断预算close异常、训练任务/奖励和BC初始化，标准化含cooldown初态后再小对照；P5全面验收、规模训练就绪和战斗收益均未建立。

## 2026-10-19 BC warm-start → PPO 最小MVP

`train_micro_ppo.py --init-bc`严格验证BC与冻结数据，仅转置复制actor，critic保留新初始化、optimizer空，与resume互斥；导出producer透传准确BC来源。本轮独立BC warm-start新分支0→32步，不是384→416；默认64与旧384不变。来源BC及metadata hash不变。训练前82真实冻结观测原始logits误差2.861e-6、masked概率误差3.8743e-7、动作82/82一致，initialization_report在learn前保存。该82条仅迁移诊断，未完成正式1000观测验收。

唯一32步训练`artifacts/micro_ppo/p5_bc_warmstart_20261019`，52.828秒、updates0→2，optimizer空→12个step4，actor finite且更新（最大参数变化.001202449），reload误差0。2完整死亡局各16步，敌最终HP15/9、官方结果/close确认；32条mask/8loops/HP奖励通过、buffer无failure/discard/专家/冲突。第32步done后SB3自动reset第三空局f9c100aede024777b7321232b3a1c3b8，预算close仍EOFError/Traceback，无官方结果/summary；0采样未入buffer、无SC2残留，关闭缺口仍未修。

actor`artifacts/models/marine_ppo_bc_warmstart_20261019`（weights SHA bccce3aa15dfda49518f8dd0bbd5a2b9949a3ed38d814291a3ad38ba9b876ec1），checkpoint SHA d81fe552b3b2a126283d3fb38b31aa8e86e69d506bd842611213ef0f9af47c9e；同82观测导出概率误差5.9605e-8、动作全同。BC/初始PPO/更新PPO argmax均[4,17,28,6,27]、0变化，概率最大更新.100795686。可用--resume该32步checkpoint继承BC来源，不重复--init-bc。

唯一部署`artifacts/runs/p5_bc_warmstart_ppo_20261019`，单Marine镜像distance6/seed20261019/max20、exit0；12推理/owned，actions[0,3,4,3,2]、10engine_confirmed+2hold，5.044643秒low_health_safety_exit、己/敌9/21；mask/8loops合法、无fallback/冲突/error、全非专家。初frame17、己cooldown5.69018555未标准化；本轮没有BC游戏或严格对照。知识迁移与多动作部署成立，不能从历史randomPPO全HOLD差异推出强度或32步训练收益。显式`.\run_ppo.cmd --ppo-model artifacts/models/marine_ppo_bc_warmstart_20261019`选用；模型/原始工件迁移另带。报告docs/PHASE_05_BC_WARMSTART_MVP_REPORT.md与docs/validation/ppo_bc_warmstart_mvp.json。下一步优先近战/射程差可学习任务和小对照，不盲目堆镜像Marine训练；预算close/cooldown标准化待办。P5全面验收、规模训练就绪与战斗收益未建立。

## 2026-10-19 近战训练接续

最新完成独立BC初始化近战PPO0→128，原BC/随机PPO384/BCwarmstart32及默认64actor保留。任务marine-vs-zergling-v6/名义距6/满HP1v1/12秒/8loops/rewardscale45，task贯穿env/Gym/worker/trainer并保存metadata；resume继承且拒绝任务冲突，旧无task元数据按Marine/6/8解释。真实enemy type105、35HPmax、近战range0.10009765625；自然回血signedloss原样按真实HP计算。

新run `artifacts/micro_ppo/p5_melee_bc128_20261019`，128步169.688秒、updates0→8、Adam空→step16、finite actor更新/reload概率误差0。9完整enemy_dead各13/14步、己10或15HP；另3步部分局budgetclose仍EOFError/Traceback且无summary/官方结局，buffer failure/discard0、无SC2/worker残留。128行mask/8loops/相邻真实HP损失与奖励复核过；128已有真obs导出parity最大1.0477379e-9、动作全同。checkpoint SHA177d1b91f420acfbdfa39e0ffc3d18b53975b23a75f394f9fe5122177b9158ea；actor `artifacts/models/marine_ppo_melee_bc128_20261019`，weights SHA4f22c0f05e428600183983244b0be2e48a024326fa1a8b404341f95d3681f0d2，producer保留BC与task。

唯一2短探索PPO/规则同seed20261019，均14决策/6.116071秒enemy_dead/己10HP；PPO actions[0,2,2,0,10]、规则[0,3,2,0,9]，无fallback/冲突/error。名义距6而ready距3.134765625，cooldown .52783203125/.417236328125不同，不能严格对照/推胜率；同128训练obs原BC与新actor argmax零变化，不能推128步收益。默认run_ppo仍64步，新actor显式--ppo-model选择，模型/证据Git忽略需另带；继续新近战checkpoint用--resume，不再initBC或换任务。

共享docs/PHASE_05_MELEE_PPO_MVP_REPORT.md与docs/validation/ppo_melee_mvp.json。仅1项实现任务契约检查+compile/CLI、唯一128步训练+2探索，无外部模型/安装/凭据/旧suite。下一步budget-close协议、初态cooldown标准化及有限独立比较；P5全面验收/规模就绪/真实训练时间截断与系统崩溃/收益未建立。

## 2026-10-19 三任务课程PPO256最新接续

唯一新增128步，从BC来源近战128恢复actor/critic/Adam→累计256，seed42/nsteps32/batch16/epochs2/lr.0003继承，154.375秒、updates8→16、12个Adam step16→32。三任务预冻结：Zergling距6/fullHP→距8/fullHP→距8/己.6（敌1、time12、scale45），按reset轮转0/1/2重复，A41/B44/C43采样步，己初HP45/45/27、敌35。--curriculum configs/micro_curriculum_v1.json --allow-task-change显式记录父/新任务集；task字段只是兼容默认A，curriculum治理reset，新run从0开始；导出producer保留task_semantics/course/taskchange/parent及BC源。

8完整局6enemy_dead+2marine_dead，完整回报均.59352不能跨任务与历史比较；末C14步己2/敌.743164预算close仍EOFError/Traceback，无summary/官方结果，异常未入buffer、无SC2/worker残留。128真8loops/mask/相邻HP奖励核验通过raw误差0，系统failure/discard/conflict/专家0；53engineconfirmed+72hold+3orderpreserved。有限actor更新max.00319707、reload概率误差0，128已有真obs导出误差5.66244e-7/动作全同；同obs父/新3argmax变化，不作训练收益。

新checkpoint artifacts/micro_ppo/p5_curriculum256_20261019/model.zip SHA9c94690a2cb8eaabfb5fd24c6c0984896825d6f27f87700335f9e41df3aaafd1；新actor artifacts/models/marine_ppo_curriculum256_20261019 weights SHA8a0e810b5e686fd71fa74f4a7f7b5be486401647b3119b4ec7bd87e1a94bbfc1。父zip/metadata不变，默认run_ppo仍原64actor，显式--ppo-model选新目录；后续resume256自动继承课程，不再initBC。工件Git忽略，迁移另带。

仅2场heldout：训练后、执行前冻结plan SHA301db03560426486423a363f5ad50704af48c61b04e48dd94428963a68d6e956，nominal距7/己.8/敌1/12秒/seed20261019，PPO/规则各1；两者13决策均[0,3,3,1,6]、5.401785714秒low_health_safety_exit、己6HP，敌.6064453125/.58935546875。可观测初态frame17/距5.892578125/HP36vs35/CD0/obs/mask一致，仅1pair非严格引擎因果对照，不推胜率/收益/泛化；低HP安全截断非死亡，不判失败或假设继续必胜。runner的distance有限(0,10]支持7在训练结束后修复，默认6及旧3/6/10保留。

规则raw split=train、前12行bc_eligible=true/末1false为旧专家默认；PPO13条validation/eligiblefalse。两run均未导出数据集/进入已结束训练，raw不改；各learning_exclusion.json及共享JSON保存rawSHA、excluded_from_future_training=true，后续不得收集为BC/PPO训练。未来探索显式--data-split test，本轮不重跑。详见docs/PHASE_05_CURRICULUM_MVP_REPORT.md及docs/validation/ppo_curriculum_mvp.json；只必要task1检查/CLI静态+唯一128训练+128真obs离线核验+2heldout，无外部模型/安装/.env/扫参/旧suite。下一步先预算close与安全边界，再新授权有限比较；P5全面验收/规模就绪/收益未建立。


## 2026-10-19 heldout完整终局评估接续

本轮未训练，NumPy curriculum256与原规则kite在同heldout Zergling距7/己.8/敌1/time12/seed20261019串行仅各1局。新增仅本地场景`--allow-low-health-eval`同时绕过场景20%退出和微操20%门禁，仍保留支持域/mask/仲裁，强制test+非专家，PPO加载/推理异常显式失败；生产默认保护与默认64actor不改。执行前plan SHA `a0bfb7c3b7fbc11c07ac078b43a5ed7de69bf936ea2e49d4e5be1e362b6ccfea`，模型/源/map等hash前后不变。

两局初frame17/HP36vs35/实际距5.892578125/CD0/完整obs与mask一致，仍未固定完整引擎状态。PPO15infer/15owned、请求[0,4,3,1,7]，frame137/6.116071429秒enemy_dead、己6HP；规则16owned/请求[0,3,3,1,9]，frame145/6.473214286秒enemy_dead、己1HP。均enemy_dead_confirmed真/own_dead假、terminated真/truncated假。低HP source6HP的PPO仍选HOLD，规则6HP和1HP仍HOLD，全部controlled=1；HOLD延续已有攻击，不冒充新增命令确认。PPO7engineconfirmed+7hold+1preserved，规则7confirmed+9hold，无fallback/conflict/error/残留，exit0。31条均test/expert=null/bc_eligible=false，各run sidecar按rawSHA永久排除训练。

外层主动leave的官方Defeat/Victory与旧summary truncated标签不能替代局部真实击杀；raw reward仍null/not_implemented，未造训练奖励。只1pair不推强度、胜率、泛化或训练收益，不以PPO剩HP/结束时间差排名；此前低HP截断并非死亡，本轮仅证明这次继续至击杀。详见[终局报告](docs/PHASE_05_TERMINAL_EVAL_REPORT.md)、[共享证据](docs/validation/ppo_terminal_eval.json)。模型/原始工件Git忽略需另带；budgetclose EOFError仍待修复，下一步新授权有限比较前先关闭协议/初态标准化；P5全面验收/规模就绪/收益未建立。


## 2026-10-19 E3完整局最新接续

唯一预冻结完整Rule+PPO局已自然官方Victory，exit0：Ancient Cistern LE、Zerg Easy Macro、非实时8loops、seed20261019，1200游戏秒/600墙秒上限均未触发。371.786游戏秒、launcher39.716实际秒；45工人/53Marine峰、58累计Marine、2基地/8兵营。233次PPO推理=233owned=233真实8loops transition，27Marine tags；767combatsteps、最多4名Marine逐个共享单体actor。动作0..4=[0,17,144,8,64]，159engine_confirmed+64hold+4preserved+6engine_unconfirmed；后两类不冒充新确认。mask合法、conflict/error/model-fallback均0，SC2自然cleanup无残留。

当前双击 `run_ppo.cmd` 默认使用 `artifacts/models/marine_ppo_curriculum256_20261019`，是本次E3联调实验模型，不表示更强或最佳；原64模型仍保留，可用 `--ppo-model artifacts/models/marine_ppo_mvp_20261019` 显式选择。默认变更发生在本局结束后，仅show-config静态核验，不追加游戏。本局使用显式run_logged命令，赛时source/model/map预冻结；赛后launcher/文档更新不冒充冻结期间变化。

生产低HP/unsupported/静态防御/控数等保护继续规则combat，不等于模型加载/推理失败fallback；没有逐原因遥测，不能推算次数。支持6敌种而课程仅1Marine对1Zergling，未记录实际敌type分布，不能排除课程外支持敌种推理；多Marine共享actor并非训练过群体策略。仅1局Easy工程Victory，无对照/统计，不推PPO收益、强度、胜率或正式P6验收。

run `artifacts/runs/e3_fullmatch_ppo_20261019`，冻结/console/执行证据 `artifacts/p6_e3_fullmatch_20261019`；报告 `docs/PHASE_06_E3_FULLMATCH_MVP_REPORT.md`，共享 `docs/validation/e3_fullmatch_mvp.json`。raw233条虽旧split=train，全部expert=null/bc_eligible=false，另learning_exclusion按SHA永久排除训练；reward仍null，未训练/未调外部模型/未改API配置/未装包/未重跑。模型及原始工件Git忽略，迁移另带；训练budgetclose EOFError历史问题仍未解决。正式P6及收益评估待新授权预算。
