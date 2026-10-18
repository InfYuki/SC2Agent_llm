# SC2Agent_llm 工作交接与换机恢复

交接日期：2026-10-18。仓库：<https://github.com/InfYuki/SC2Agent_llm>。

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
| P5真实训练桥接MVP | 单Marine真实reset/step通过，未正式验收 | 自定义Gym风格API、14步真实8loop证据；非Gymnasium Env，PPO未开始，见 `docs/PHASE_05_ENV_MVP_REPORT.md` |

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

不要先安装一整套旧项目依赖或直接开始PPO。当前生产环境没有stable-baselines3/sb3-contrib训练栈；后续应另建训练环境，保持Ares运行基线可用。已有BC权重和训练元数据位于本机artifacts/models；无运行中的训练进程，PPO尚未开始。

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

> 先读HANDOVER.md、README_LOCAL.md、docs/PHASE_04_MVP_REPORT.md和P3_COVERAGE_REPORT。项目在C:\code\SC2Agent_llm，目标是本地Ares＋LLM战略＋Marine微操，不参加AI Arena。用户偏好快速可用MVP、少重复测试；每小步交子代理，主代理协调核对。P1/P2与P3历史证据保留。P4以冻结82条（32/24/26）训练NumPy BC，val选epoch1000，test准确率88.46%；这是标签拟合工程原型，不证明收益或泛化。显式run_bc.cmd --bc-model启用，默认仍规则；失败规则回退，BC日志不充当专家标签。模型和数据不在Git，迁移需另带。未开始PPO，训练就绪仍未建立。遵守唯一命令出口、非阻塞LLM及凭据保密。

## 2026-10-18 P3接续状态

suite marine-coverage-v7 / 场景*-v6正式批次 `p3_v7_formal_20261018_115352` 24/24通过；冻结82条技术合格样本，train32/validation24/test26，每split五动作均出现。共享摘要在docs/validation/micro_coverage_v7.json和micro_dataset_v7.json。58/58单测、pip check、diff检查、独立源码审查与最终数据/日志验收通过；suite记录17源哈希，当前无变化。双AI结束屏障要求双方原SDK返回有效官方Result后清理；24局日志均有双方官方Result、无连接已关闭错误，0命令冲突。失败v5（0.6秒初始化窗口不足）和v6（双AI退出竞态）保留且不导出；详情见 [P3覆盖报告](docs/P3_COVERAGE_REPORT.md)。

两种专家各9次低血量安全退出、1次敌人死亡、2次时间上限，未发现优势证据。相同双目标几何不同seed不能作为泛化证明。本段为P3历史状态；P4已完成小样本BC原型，训练就绪仍未建立、PPO未开始。场景局部结果优先读scenario_result.outcome和尾transition.end_reason，summary.stop_reason仍有统一写game_time_limit的分类限制，后续连同Telemetry映射修复。

## 2026-10-18 P4接续状态

快速BC原型已训练并接入 `run_bc.cmd`，双击即按脚本目录定位本次模型；`--bc-model <目录>` 可覆盖，默认模型缺失仍规则回退。NumPy MLP、masked交叉熵和Adam；train优化、validation选权重、test最后评估一次。训练/验证/测试准确率100%/100%/88.46%。新增6项必要定向测试（训练2、运行4）与CLI检查通过，本轮不重复全58项或24局suite。最终推理一致性与两局smoke证据见 [P4报告](docs/PHASE_04_MVP_REPORT.md)。

模型本体不提交；换机单独复制模型目录和冻结数据，或按README重训。82真实行推理一致、两局场景smoke通过；1000条真实及边界一致性未做，P4未正式验收。下轮先P5单Marine Discrete(5)最小reset/step/action_masks/close与奖励桥接；stub仅契约，真实SC2接线后才称可训练。PPO未开始，小样本准确率不证明BC优于规则。


## 2026-10-18 P5真实桥接MVP接续

SC2MicroEnv自定义Gym风格reset/step/action_masks/close已接真实worker；不是Gymnasium Env，死亡可obs=None。唯一真实episode c06761effef34708901c214e7d7c3bd7，seed42/8秒上限，14步全部8loops，frame17→129；action5及masked0拒绝不推进。HP己45→0/敌45→9，逐条复算奖励一致，总-1.2含死亡终局-1；marine_dead/terminated=true/truncated=false。双方官方Defeat/Victory、worker exit0、close无自有SC2残留；0命令冲突，RL日志非专家/BC合格0，不读LLM凭据。

首次pre-game目录冲突失败已保留，worker Telemetry改game子目录后只运行上述1局。2项必要父端契约测试与worker编译/CLI通过；不重跑全suite。真实time truncation、敌死、重复reset、mid-close、故障与训练吞吐未验证。完整报告docs/PHASE_05_ENV_MVP_REPORT.md，共享docs/validation/micro_env_mvp.json；真实奖励消费RL rollout，旧micro_summary.reward字段与通用summary截断分类不作为环境终止依据。PPO未开始、训练就绪未建立。下一步补训练适配/必要边界与吞吐，再独立训练环境接PPO。
