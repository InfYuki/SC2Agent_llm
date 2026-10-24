# SC2Agent_llm 工作交接与换机恢复

## 2026-10-24 基地防御与 Orbital Command

新增 Missile Turret（含 Engineering Bay）、Bunker 和 Orbital Command 的建造／升级链。LLM 可选 `base_defense: none|standard|fortified` 与 `orbital_command: true|false`，旧策略缺字段默认 standard／true；原兵种路线、经济、Stim 与赛后人工学习开关保持兼容。Bunker 可装载附近 Marine 并在安静转场时卸载；Orbital 可召唤 MULE，并针对本局实际观察到的隐形／埋地威胁 Scan。防御不等于完整防空军队，也不把回放全图事实作为当前可见敌情。

装载和建筑技能都由规则控制，Marine 的16维／5动作 PPO 不变；装载前退出旧控制轨迹。轨道升级使用有界储备，避免持续排 SCV 导致永远无空闲，也避免无限期停工。仍用 `.\run_human_training.cmd --human-fullscreen`，赛后仅显式 Y 才学习。本轮未新开实战或训练模型，详见 [基地防御与轨道报告](docs/TERRAN_DEFENSE_ORBITAL_REPORT.md)。任务结束清理本轮安全缓存，保留回放／模型／学习证据和依赖。

## 2026-10-24 Factory 全兵种生产与基础控制

Factory 路线现覆盖 Hellion、Hellbat、Widow Mine、Cyclone、Siege Tank、Thor。LLM 在旧编成外可选 `factory_hellion_cyclone`、`factory_mine_tank`、`factory_thor_hellbat`；气矿、Factory、附着 Tech Lab、Armory 与首批单位资源由统一生产计划衔接。Hellbat 可直接生产或由 Hellion 转换，Widow Mine 下埋后自动攻击并在转场时收起，Thor 保留两种武器模式的控制；Cyclone 本轮只实现基础武器作战，暂不含 Lock On 风筝。

这些机械单位由规则控制，不进入 Marine PPO。扩张、补工人、矿气分配、Stim 研究和原有兵营编成保持兼容。仍用 `.\run_human_training.cmd --human-fullscreen` 开局，赛后仅显式 Y 才学习。本轮未新开实战或更新模型；新生产链尚待下一局验证，不能将定向检查当成实战收益。详见 [Factory 生产链报告](docs/FACTORY_UNIT_PRODUCTION_REPORT.md)。本轮最近两局复盘另见单独报告，未批准局不补学。


最近两盘 `human_20261023_203244_532216` / `human_20261024_110526_233695` 均自然败局、约16分07／08秒，都是已批准学习的有效局；经济修复已达到4基地，后一局 Stim 已完成研究并出现施放记录。两局 PPO 均为0样本，未更新参数。对手回放累计生产17／11艘 Battlecruiser，现已修正压缩经验遗漏BC的问题，仅刷新已批准局的回放经验，原学习报告与PPO指针未改。优先改进为可见空军后的防空编成、早期pending扩张与补工人时序、微操支持域与拒绝原因，详见 [最近两局复盘](docs/LATEST_TWO_HUMAN_MATCH_REVIEW.md)。

## 2026-10-24 Stimpack 研究与战斗使用

LLM 的 `research_priority` 现支持 `[]` 或 `["stimpack"]`，旧空列表策略保持合法。Ares 的 `UpgradeController` 负责建造所需兵营 Tech Lab、研究升级及 pending/complete 去重；LLM 快照包含可选科技和研究状态。这是科技选择和执行接口的第一项，尚不是自动学习所有科技树或远端模型微调。

Marine 和 Marauder 的 Stim 由规则按已完成升级、生命值、现有 Buff 与可见交战条件触发。Stim 是独立技能，不扩展 Marine PPO 的16维/5动作契约；施放决策前关闭旧微操轨迹，该决策不采样 PPO 动作，避免把技能当作伪训练动作。仍用 `.\run_human_training.cmd --human-fullscreen` 开局，赛后仅显式 Y 才学习。新研究/施放尚待实战验证，详见 [Stimpack 与临时文件清理报告](docs/STIMPACK_AND_CLEANUP_REPORT.md)。

任务结束前清理本任务临时产物和安全缓存；保留模型、checkpoint、训练与学习记录、回放、证据报告、依赖和私密配置。此约定已写入根目录 [AGENTS.md](AGENTS.md)，下方旧“暂不研究/无 Stim”等说明为历史能力，不覆盖本节。

## 2026-10-24 兵营完整兵种生产链

当前目标仍是战胜用户本人。本轮补齐标准对战兵营的 Marine、Marauder、Reaper、Ghost 生产入口及基本规则控制，LLM 可以选择对应兵种路线，科技与资源由 Ares 执行。Marauder 需要兵营 Tech Lab；Reaper 不需要 Tech Lab；Ghost 需要兵营 Tech Lab 和 Ghost Academy。Tank/Medivac 原有生产控制继续兼容。新增 `marine_marauder_medivac`、`reaper_pressure`、`ghost_support` 三种编成，原 `marine_basic` / `marine_tank_medivac` 保持合法且默认仍为后者。新步兵由规则执行攻击、集结与撤退，暂不含技能研发或 Ghost 主动施法。

Marine PPO 的16维观测与5动作接口保持不变，新增兵种由规则控制，不把它们混进旧 Marine 模型。仍用 `.\run_human_training.cmd --human-fullscreen` 开局，赛后仅显式 Y 才学习。新兵种生产与基本控制尚待下一场真人对练验证，不将离线检查当成实战胜利。具体可选配置及本轮验证见[兵营生产链报告](docs/BARRACKS_UNIT_PRODUCTION_REPORT.md)。

## 2026-10-23 真人赛后学习改为人工确认

照常运行 `.\run_human_training.cmd --human-fullscreen`。对局结束后终端询问 `Learn from this match (LLM + PPO + replay)?`：输入 `y` 才更新 LLM 经验、PPO 和复盘经验；输入 `n` 跳过，直接回车或终端无交互则保留待定。原始记录均保留。可用 `--learn no` 预设本局不学，`--learn yes` 显式预先允许自动学习。暂时跳过后，可运行 `.\run_human_training.cmd --learn-run <run_id> --learn yes` 补学，不会打开游戏；成功消费的 PPO 不会重复训练。直接调用 learner 或复盘经验写入也检查批准和永久排除。

用户指定不算的退出局 `human_20261023_200418_872055` 已永久排除，备份共享经验后从其余三局重建 LLM 聚合经验，防止只删记录而残留 lessons。该局约50.09秒，原记录显示 Agent Victory，但不计有效战果；PPO有效样本0、未更新模型。后继有效局 `human_20261023_200655_490506` 的161条PPO样本、27段轨迹、6次优化保留，最新模型指针未改。后继 LLM 在当局可能已读取退出局经验，这部分历史影响无法追溯撤销。详见[人工学习开关与排除报告](docs/HUMAN_LEARNING_APPROVAL_REPORT.md)。下方旧“赛后自动学习”说明为历史流程，以本节为准。


## 2026-10-23 真人对练经济修复

当前目标仍是战胜用户本人。本轮针对第二局长期矿少气多、双基地发展受限，改进扩张、持续补 SCV 和动态矿气分配。继续运行 `.\run_human_training.cmd --human-fullscreen`，LLM 与 Marine PPO、赛后学习入口保持启用。

新增共享经济执行策略：默认72工人/4基地为发展愿景，工人目标按现存矿点和可用气矿容量约束、上限80，工人损失后继续补充；二、三、四基地分别在约2、6、9分钟后允许推进。LLM 可提出经济目标，但本地资源饱和/枯竭底线仍生效；危险扩张暂停，施工中避免重复预留。混编时气体库存过高且缺矿，将每气矿目标从3工降到1工，气不足时恢复3工，Ares 负责实际撤气回矿；纯 Marine 配置不再持续采气。

每15游戏秒记录 `economy_policy`，包含请求/执行目标、当前/供给工人数、ready/pending基地、矿气库存、目标与实际气工人数，LLM快照也能读取执行状态。本轮为经济逻辑改进，未新开真人比赛，尚待下一局观察实际经济效果。详见[经济修复报告](docs/HUMAN_ECONOMY_REPAIR_REPORT.md)。下方首局和“新兵种待验证”等文字保留历史；第二局已实际生产坦克/Medivac，并完成 PPO 更新。


## 2026-10-22 当前最高目标：战胜用户本人

用户已完成首盘真人 Terran 对练，当前最终目标改为让 Agent 战胜用户本人；官方最高难度 Bot 仅作为练习基线，不能覆盖此目标。当前两项工作是基于真实回放观察用户运营并供 LLM 下一局战略参考，以及先补 Siege Tank / Medivac 的科技、生产与控制，再逐步增加其他单位。首盘自然 Defeat、536.651785714 游戏秒，LLM 跨局提示经验已更新；有效 PPO 样本0，已明确跳过，没有 PPO 参数更新。单局观察不能当成用户永久习惯，回放得到的历史全图事实也不能当成本局实时敌方视野。实现与分析见[真人对手与坦克医疗运输机报告](docs/HUMAN_OPPONENT_TANK_MEDIVAC_REPORT.md)。

现规则默认及LLM支持 `marine_tank_medivac`（Marine80%/Tank12%/Medivac8%单位数目标），旧 `marine_basic` 仍合法；Mining + GasBuildingController补气，100游戏秒后科技与首批支援单位资源储备在Marine消费之前，Ares TechUp推进Factory/TechLab/Starport。Tank架起/收起、Medivac治疗/跟随/可见防空避让由独立规则控制，不进Marine PPO feature/action。原来MicroRuleBot重置arbiter后补回support所有权，保留Marine已发命令；无Marine也继续控制Tank/Medivac。无空投/升级/Stim，新混编尚未真实对局验证。

首局replay实际解码并写 `replay_analysis/` 与共享 `strategy_memory.json`，真实LLM请求payload注入检查通过。build98370无精确schema，本轮显式批准98310兼容解码并校验玩家/胜负/时长；详细时间线、依赖与复现见[首盘复盘](docs/HUMAN_OPPONENT_FIRST_REPLAY_REPORT.md)。共享memory-dir的 `replay_protocol.json` 持久保存仅98370→98310配对，正常赛后先找精确schema，再按该显式配置自动复盘，不必每局手动输入；每局仍校验并标记兼容，其他build或未配置时明确skip，不静默猜协议。本局已不带CLIoverride重新解析，selection为persisted_explicit_compatibility_pair。10项生产/战略/LLM+PPO组合检查、1项经验注入检查及新增非法配对拒绝检查通过，无新SC2对局或API请求；不能宣称已战胜用户。

### 2026-10-22 真人入口启动修复：Git 元信息不再阻塞对局

用户首个实际启动 `human_20261022_162220_645926` 在打开游戏前因 `subprocess(["git", ...])` 报 WinError 2；当时 PowerShell 能找到 `git.cmd`，但 Python 的 Windows CreateProcess 无法将裸 `git` 解析成该批处理入口。现直接定位原生 `git.exe`（含本机 `C:/Program Files/Git/mingw64/bin/git.exe`），统一采集版本信息；完全缺少 Git 时记录空 commit/diff、显式警告及范围有限的源码哈希，不阻塞游戏、不伪造版本。fallback 只读取 Python 源码与启动脚本，不递归读取私密配置或 artifacts。

回归检查走真实 `run_local.main` 的 manifest/结果保存路径，仅替换 SC2 执行，分别验证 PATH 无 Git 但存在原生程序、以及完全无 Git 两种情况；不是再次只检查会提前返回的 `--show-config`。未启动游戏或调用 API，真人双窗口与完整学习仍待用户重试。PowerShell 实际开局用 `.\run_human_training.cmd --human-fullscreen`；`--show-config` / `--check-only` 不开游戏。

## 2026-10-22 当前推进：真人 Terran 对练，LLM 与 PPO 同开

用户新优先事项是人类作为 Terran 对手，赛后让 LLM 指挥经验与 PPO 微操一起迭代。新增 `run_human_training.cmd`，启动 HumanTerran（玩家操作）与 LLM_PPO_Training 两个实时客户端。默认 Ancient Cistern LE、LLM最多240请求、448 PPO+交战门禁、最多4Marine，无默认时间截断。普通官方Bot入口仍默认CheatInsane；真人对局无官方难度概念。

赛后自动调用独立训练解释器 `tools/learn_human_match.py`：只接受自然完成且有真人采样来源的对局；LLM写入有界跨局提示经验（不做远端权重微调），PPO使用冻结行为checkpoint对应的随机masked采样、实际帧间隔奖励与按Marine ownership分段的GAE进行小规模真实梯度更新。更新actor/critic/optimizer checkpoint并导出NumPy actor，发布成对的最新指针，下次入口自动采用。行为概率与权重来源核对，不把旧argmax评估数据、replay或BC标签当成on-policy训练。

每局 `artifacts/runs/human_<timestamp>/` 保存replay、事件、胜负、`human_training.json`、`human_ppo_rollout.jsonl`、`learning_report.json`及 `learning/` 模型；共享经验与 `ppo_latest.json` 位于 `artifacts/human_training/memory/`。LLM/PPO分别报告updated/skipped/failed；PPO不足8样本跳过、失败保留旧指针，成功消费的轨迹不重复训练。中断/错误/限时截断不训练。真人对局实时帧可能跳帧，记录实际间隔，不冒称固定8loops。

SDK真人+Bot结果为列表，按Bot槽提取；本入口协调两个官方终局与host回放，局部清理每个自有客户端，避免SDK任一退出时全局kill另一客户端。现接口仍仅Marine局部微操，坦克/空军/静态防御等不支持时规则接管。入口预检、离线合成采样真实PPO更新与必要正确性检查通过；本轮未启动真人对局、未调用API，不声称真人实战已验证或训练带来强度提升。用户双击入口、正常结束后等待终端赛后处理即可开始。详见[真人训练入口报告](docs/HUMAN_TRAINING_ENTRY_REPORT.md)与README顶部。

## 2026-10-22 当前最高目标（优先于下方历史阶段记录）

永久项目目标：战胜最高难度官方Bot，获胜优先；胜局越短越好、自然败局越久越好。完整局默认CheatInsane。用户要求围绕实战结果快速推进，不为每项改动反复卡严格提升证明；必要正确性验证及事实记录仍做。

推荐 `run_ppo.cmd`，默认448 actor（`artifacts/models/marine_ppo_two_enemy448_20261021`）+交战门禁；`run_llm_ppo.cmd` 同配置、用于需要LLM时。末尾参数可覆盖，`--no-ppo-engagement-gate` 可关闭。通用规则入口仍为纯规则、对手最高档；新评估矩阵默认448+门禁只作用E3/E4，旧plan不改命令，P5脚本微操对手不变。

本轮通过真实 `run_ppo.cmd` 省略difficulty/model/gate验证默认值：Zerg/Ancient Cistern LE/seed20261020/nonrealtime8loops/最多4Marine/LLM0，run `p6_highest_goal_20261022` 自然Victory，401.428571游戏秒（6分41.43秒）、completed/exit0/stop及error null。默认最高档+可用配置+本轮最高档虫族胜出目标已达成，建立401.43秒基线；不保证所有race/seed稳定赢。

一次运行无重试，338合法8loop推理/owned/raw、266 confirmed/3 unconfirmed/8 preserved/61 hold，冲突/fallback0，回放存在/无残留。3项定向组合检查、核心scope及源/地图/actor冻结检查通过。原始评估永久禁训，模型和工件Git忽略换机另带。排序按可比配置自然胜局优先、胜局时间升/败局降；draw/cap/error/invalid不排名，不把错误或截断叫“活得久的败局”。

来源HEAD `7f8824a8cafe618e5ea1c8cddd345b0395e4e309`+运行dirtydiff `114f38a540afec4d991d89963eb5986415044997f3ba570de0cb030311abd3b0`；evidence SHA `6c7e1c87f597139ee3808ae1ae9078a4b128871110774904d891b7edbc9f952f`。详见[最高目标报告](docs/PHASE_06_HIGHEST_BOT_GOAL_REPORT.md)、[精简JSON](docs/validation/p6_highest_bot_goal.json)及 `artifacts/p6_highest_goal_20261022`。后续继续最高档缩时、可扩其他种族/种子；职业回放可后续按需获取。本轮本地保存，未自动push。下方Medium、256和门禁off均为旧阶段记录，不覆盖本节。

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
| P6统一评估矩阵 | E3/E4完整局工程MVP与E0–E4离线汇总可用；正式评估未完成 | 所选3 attempts含1 crashed，E0–E2 missing；见 `docs/PHASE_06_EVALUATION_MATRIX_MVP_REPORT.md` |

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


## 2026-10-19 E4 LLM战略 + PPO微操完整局接续

`llm_ppo`已组合既有后台LLM目标与curriculum256 PPO微操，共用单RuleBot/arbiter；新双击入口`run_llm_ppo.cmd`（默认realtime/Medium/调用上限60），本次实验显式非实时Easy且收紧预算，不改变`run_ppo.cmd`默认。运行示例：`.\run_llm_ppo.cmd --difficulty Easy --no-realtime --llm-max-calls 16`；实际已完成命令/冻结SHA以报告为准，不应直接重跑覆盖既有run-id。

首次唯一局273.214游戏秒因可选latest_state.json原子替换WinError5崩溃、exit1、无官方结果/回放；4真实HTTP200/4active、231LLM经济步、166军队目标步、110PPO。证据代理局中Get-Content读快照可能触发Windows删除共享锁，但未证实因果，失败日志完整保留。只修可选快照winerror5/32有限重试/skip，其它必需写和异常不吞；必要同配置/seed重验一次，无第三局、无挑策略结果。初cap20已用4，重验cap16实际6，累计10≤20；未改API配置/提示词/模型/时效门或训练。

重验run `e4_fullmatch_llm_ppo_20261019_snapshotfix`自然官方Victory、exit0，370游戏秒/39.858实际秒；6HTTP200/6valid active、428LLM及经济目标步、361军队目标步、251等待callbacks。240PPOinfer=owned=240真8loops，25Marine tags、mask合法；其中102PPO命令/34owned微步/17tags发生于LLM实际激活区间。159engine_confirmed+71hold+3preserved+7unconfirmed，后者不冒充确认。43工人/56Marine峰、生产60、2基地/8兵营快照、采矿8020；零冲突/模型fallback/重验error/残留，replay保存。snapshot锁retry/skip均0，不声称实机复现了锁修复。

两run共350行均expert=null/bc_eligible=false，旧split=train文字由按rawSHA永久learning_exclusion排除训练，reward仍null。保护继续规则、最多4Marine共享单体actor、敌type与逐保护原因未记录；一个Easy成功样本加一个中止局不推强度/胜率/训练收益。训练budgetclose EOFError历史缺口仍在，正式P6未完成。模型/raw Git忽略需另带。完整双attempt、异常/观察干扰边界、plan/source/model/mapSHA与cleanup见 `docs/PHASE_06_E4_FULLMATCH_MVP_REPORT.md`、`docs/validation/e4_fullmatch_mvp.json`。

## 2026-10-19 P6统一离线评估矩阵接续

新增 `tools/report_evaluation_matrix.py`，统一E0 Rule/Rule、E1 LLM/Rule、E2 Rule/BC、E3 Rule/PPO、E4 LLM/PPO；只读指定历史run，不启动游戏/API/训练。JSON及Markdown已生成于 `docs/validation/p6_evaluation_matrix_mvp.json` 与 `docs/PHASE_06_EVALUATION_MATRIX_MVP_REPORT.md`。需要原始artifacts另带；仓库根目录复现：

```powershell
python -s tools/report_evaluation_matrix.py e3_fullmatch_ppo_20261019 e4_fullmatch_llm_ppo_20261019 e4_fullmatch_llm_ppo_20261019_snapshotfix --output docs/validation/p6_evaluation_matrix_mvp.json --markdown docs/PHASE_06_EVALUATION_MATRIX_MVP_REPORT.md
```

本轮所选3 attempts：E3 completed/Victory 1，E4 crashed/unknown 1与修复重验completed/Victory 1；E0–E2 missing，不能把历史P1/P2/BC证据自动当成本轮配对。失败完整保留分母、unknown不记竞赛负或胜；已知结果2/2与端到端Victory 2/3只描述所选工件，E4完整1/2，missing比例null。局部micro截断不是整场截断。调用者须提供所选轮次全部attempt，工具不会自动证明无遗漏。

缺game_build、E4缺LLM模型记录、共享源码SHA存在差异，E4 cap20→16与修复重验也不是独立同配置种子；公平配置不完整，不构成正式P6或强度/泛化/训练收益结论。工程可运行与正式比较资格分开记录，不从Easy单局推收益。下一明确小步是统一固定配置的小预算runner，冻结配置和attempt清单、补齐缺失模式；未来游戏/API预算另行授权。本历史轮次无新游戏/HTTP/训练，原始工件及模型保持原样，budgetclose历史缺口仍待解决。

## 2026-10-20 P6固定配置runner最新接续

`tools/run_evaluation_matrix.py` 默认dryrun冻结plan不启动游戏，显式`--execute`顺序运行每个选中模式一次；用`--resume <batch目录> --execute`只执行pending。失败/unknown/interrupted不重试，碰撞不覆盖且foreign raw不入离线报告。plan保存完整attempt清单、固定配置、源码（含未跟踪实现）/解释器/模型/实际安装地图SHA；每局前复核，变化拒绝。批次锁与全仓runner执行锁不协调其它手工启动器，陈旧锁须先核实owner PID已退出；不读活跃latest_state。LLM总cap默认0、最多20，预分配E1/E4且未用不转移；本轮未执行LLM模式。

真实唯一batch `artifacts/evaluation_batches/p6_runner_e0e2_20261020`，固定Ancient Cistern LE/Zerg Easy/非实时8/seed20261020/控4，1200游戏秒/600墙秒，E0/E2各1、0请求/0训练。run `p6_runner_e0e2_20261020_E0`与`_E2`均completed/官方Victory/exit0/回放/无SC2残留，353.571429/354.285714游戏秒、37.328/34.656 runner墙秒；0conflict/summary.error=null。全终态后唯一resume execute exit0、0.415秒，无新增局、原attempt时间/PID/证据保持。无失败重跑或补局。

BC仍`artifacts/models/marine_bc_mvp_20261018_seed42`，weights SHA e36cba313c1d8e1731573595b1b975316e1522db3af8d1a4abf4f21e405c2dcf；248infer=owned=248实际8loops、24tags、mask合法，动作[0,2,120,9,117]，125engine_confirmed/117hold/2preserved/4unconfirmed，不能全称命令确认；无模型fallback事件。78局部truncated不是整场截断。248行validation/expert=null/bc_eligible=false/reward=null，新增learning_exclusion按rawSHA永久排除未来训练，未改旧artifact/模型/默认PPO。

plan规范化SHA6da47137d7e0f5c4952f6c8d0c6030673c529094e6204491f4488e1517496d01；运行时HEAD9f896dee、未提交runner/test按实际SHA冻结。两局map/source相同，赛后复核source/model/map身份未变；报告文档在resume结束后写。两原始manifest仍缺game_build，本批E1/E3/E4 missing，不并历史轮次、不推强度/胜率/泛化/BC训练收益；正式P6未完成、训练budgetclose EOFError仍未修。

完整命令/锁/恢复限制、各日志和回放SHA、batch state/aggregate见[runner报告](docs/PHASE_06_MATRIX_RUNNER_MVP_REPORT.md)与[共享JSON](docs/validation/p6_matrix_runner_mvp.json)。模型和原始batch/run Git忽略需另带。本轮仅必要1项合并定向测试/help/diff与原生独立scope审查后上述两游戏+终态resume，无外部模型开发子代理/安装/凭据读取。下一步新授权小预算补缺失模式/独立seed、记录build，避免直接把小样本工程运行作正式比较。


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


## 2026-10-21 P4 单规则专家 subset MVP最新接续

evaluate_micro新增显式--case/--expert与pending-only --resume，默认旧12×2不变；仅显式dual_zergling_train（规则kite，非PPO/新算法）。唯一case seed101/名义距6+8/第二敌半血/12游戏秒/120墙秒，exit0、subset1run passed，无retry。实际initial frame25己45HP/CD.19018555，两type105敌距3.134765625/5.134765625、HP35/17.602539；初态运动/回血/cooldown未标准化。12raw均16obs/5mask/合法8loops，4confirmed+8hold，末frame121/5.4017857秒low_health_safety_exit truncated、己5HP/余1敌；未全杀，不把外层leave Defeat或stop_reason当局部结论。

11eligible=4confirmed+7hold冻结独立新NPZ，末截断hold剔除；版本marine-kite-v1，label为eligible.executed_action，无expert_label伪字段。单group train11、动作[0,2,2,0,7]缺0/3、validation/test0；仅合法可供未来训练小样本，不能直接BC结论/训练readiness。export尊重rawSHA learning_exclusion（排除/无效即拒绝），本次专家raw无排除sidecar；旧82不改/不merge、不训练。新NPZ SHA f470c852696f6eb7a56f76cf0493544bd5d9a783ec3287ecd1dd0fe37b82b39a，raw SHA6d178d167a695bcc7917637af7f96d9aa9436c779f5afd58244f797fc5213317。

plan SHA e7a9581ce3441d28c56f5cc9048c2d3389158053c9b8eff78634299769ba1e62，25源码/地图前后同；pending0全终态唯一resume exit0/.265秒/0新增游戏，raw所有hash+mtime与旧82两文件hash+mtime不变，无SC2残留。suite artifacts/micro_suites/p4_expert_subset_20261021、新dataset artifacts/micro_datasets/p4_expert_subset_20261021。详见[专家subset报告](docs/PHASE_04_EXPERT_SUBSET_MVP_REPORT.md)与[精简JSON](docs/validation/p4_expert_subset_mvp.json)。工件Git忽略迁移另带；不推强度/胜率/泛化/收益或P4P5P6全面验收。默认curriculum256不变；无训练/LLM/API/完整Easy/安装/额外测试游戏/凭据与live快照读取。本轮待root保存、未push。

## 2026-10-22 P6 VeryHard 两局工程对照最新接续

仅显式提高本轮内置Zerg至VeryHard；Ancient Cistern LE/no-realtime/8loops/seed20261020/1200游戏秒/每局600墙秒/最多4Marine/LLM0。冻结HEAD08129d7，同规则宏观E0与显式448 E3各1局串行，均completed/官方Victory/stop_reason及error null、exit0、有回放；366.428571/384.285714游戏秒、launcher38.218/37.703秒，总75.921，无重试/补局。峰worker/Marine/base分别44/54/2与44/52/2，Marine生产61/64；矿采样峰390/445、气峰0，库存与生产不当兵损。E3游戏时间多17.857143秒，n1不证明胜率或收益。

E3 inference=owned=raw468；313confirmed/142hold/9unconfirmed/4preserved，后三者不冒充新确认命令，无模型fallback/conflict。guard维持默认false，448声明ZERGLING1/2；源obs13的12格受支持非飞行敌数>2共170/468（域外下界），其余1/2因缺type记录仍未知，domain-check0不能写域外0。低HP/support/mask保护不改；raw split=train非训练许可、expert null/bc_eligible false/reward null，rawSHA df43f49d05742595180d3dde4022c24839e2b9b9c6da3f9c9818af55223709d4 learning_exclusion永久排除未来训练。

P5微操敌方是BotAI脚本nearest-attack，整局Difficulty与其无关，本轮只属P6更难完整局观察。历史Easy五模式旧revision/不同actor，仅描述性参考，不能作严格难度因果。见[VeryHard报告](docs/PHASE_06_VERYHARD_PAIR_MVP_REPORT.md)及[精简证据](docs/validation/p6_veryhard_pair_mvp.json)；freeze/evidence/两run回放位于artifacts，Git忽略迁移另带。两manifest冻结源/地图一致、actor及安装地图前后不变、base_build98370；完整隐藏初态未固定。无训练/API/额外游戏测试/新工具或源码配置修改/凭据内容输出，默认difficulty/actor256/guardfalse不改；P5/P6全面验收及收益未建立。本轮本地提交保存、未push，后续实验需新预算。

## 2026-10-22 P6 CheatInsane 两局作弊压力测试最新接续

显式提高至本地API枚举最高档CheatInsane，属于作弊压力测试、不冒称中文“专家”或公平难度比较。唯一源码变动run_local.py choices增加CheatVision/CheatMoney/CheatInsane并在help注明压力测试；默认Medium、两入口curriculum256/guardfalse不变。冻结HEADaf7ad14加dirty diff SHA b003ab6ba629b50550972551c2a9e563bc7bb239f0cfb1e3b2192ca15f8c4379，实际run_local SHA3e011748b49296a0679a62cb1310cd1c22a666603b19246c5b5820b6b52395fe。相同Zerg/Ancient Cistern LE/seed20261020/nonrealtime/8loops/4Marine/LLM0，1200游戏秒与每局600墙秒预算；E0规则、E3显式448串行各1局，无补局/训练/API。

两局均completed/自然官方Victory/stop及error null、exit0、有回放；442.142857/541.785714游戏秒，launcher39.656/53.922秒，总93.578。E3比E0晚99.642857游戏秒；旧VeryHard同名义配置366.428571/384.285714秒仅历史描述，各模式n1不推普遍难度因果/退化或学习收益。峰worker/Marine/base为45/59/2与45/72/2，Marine生产86/128、矿库存采样峰1120/1940；库存生产不当累计损失，最后采样早于官方终局。

E3实际1306推理=owned=raw，mask合法/实际8loops，无模型fallback/conflict；721confirmed/543hold/23preserved/19unconfirmed，后三类非新增引擎确认。guardfalse，obs13×16的近处受支持非飞行敌数>2为370/1306（28.33%）确定超出448声明数量域下界；其余1/2缺type仍未知，0domain checks不等于0OOD。233control_released/5unit_death为局部ownership终止，不当全军损失或整局截断。raw SHA bd5faea46dd87fab20eaf5c6ff7b38b2076e8750d359af932950cad7804659f1永久learning_exclusion，split=train非训练许可、expert null/bc_eligible false/reward null。

见[CheatInsane报告](docs/PHASE_06_CHEATINSANE_PAIR_MVP_REPORT.md)与[精简JSON](docs/validation/p6_cheatinsane_pair_mvp.json)，来源artifacts/p6_cheatinsane_pair_20261022冻结命令/哈希及双runs/回放。两manifest源/地图一致且匹配freeze/dirtydiff，map/actor前后不变，base_build98370但完整隐藏初态未固定；终态无SC2/run_local残留。P5脚本微操对手不受整局Difficulty影响；没有从记忆断言作弊倍数/机制。仅P6工程压力观察，P5/P6全面验收、胜率/收益/泛化未建立；无新增遥测、安装、额外游戏测试或默认切换。本轮本地保存、未push；原工件/模型Git忽略迁移另带，后续实验需新预算。

## 2026-10-22 P6 可选PPO交战时机门禁MVP

新增显式 `--ppo-engagement-gate`，默认off，仅生产rule_ppo/llm_ppo：CDready且所有局部支持enemy均在己有效groundrange与敌ground威胁range（双方radii+entry1.0）外才交回现有RuleBot宏观；oldowner额外exitbuffer.5。CD>0或unknown几何保留，低HP/support/mask/排序/最多4Marine及训练scenario/reward不改。actor仍448显式选择、默认两入口256，敌域guardfalse；未自动promote。5相关定向tests一次通过、独立scope通过，无历史全suite。

唯一新CheatInsane E3 `p6_engagement_gate_e3_20261022`，与历史同名义Zerg/Ancient Cistern LE/seed20261020/nonrealtime8/4Marine/1200gamecap/600wall，0训练/LLM/API/重试/补局；completed/自然Victory/exit0/stop与error null，有回放/无SC2残留。406.428571game/40.390433launcher墙秒，比历史无gate E3 541.785714少135.357143游戏秒；旧E0 442.142857只作历史n1参照。运行代码已改、轨迹不同，不能称同冻结源码因果配对/模型训练收益/胜率或泛化。

324infer=owned=raw，mask合法/实际8loops；252engine_confirmed/61hold/8preserved/3unconfirmed，后三者非新增引擎确认。1213候选checks=300readyoutside拒绝+692CD保留+221己射程保留，accepted913≠owned324；633去重checkevents/206reject，拒绝无同tagframePPO overlap。103原owner拒绝同frame释放并交回本地macro；128macro均attack/command_accepted true，仅本地出口接受，非引擎确认。旧同筛法CDready/nearest>7/两attackmaskfalse为735/1306→19/324；19全retreat距7.028–7.358、oldowner buffer1.5/own_attack_range，属设计hysteresis。旧缺type/range，735不等于几何门禁必拒数，不能称全部冗余退却。

140/324 source enemycount>2为448声明数量域外下界，其余缺type未知，guardfalse/0domainchecks不等于0OOD。324行expert null/bc_eligible false/reward null，rawSHA77137bf3de5b0f6d14715f7b83fb64f4d9a0c3cb3d68817d1bfc1836a734994d按sidecar永久排除未来训练；split=train非训练许可。低血安全/冷却中合理撤退仍保留，不把所有retreat等同错误；生产库存非全军损失，P5/P6全面验收尚未完成。

冻结HEAD e3b28651c69ba5ee7dd3fd8a683328d24d3fc850加dirtydiff1a192d60b2fb8d978fc66f6ca3e827d6d862390dd8c7b683a6382f1b8efda721，map/448与历史同、manifest全源匹配且事后runtime/assets不变，base_build98370/隐藏初态未完整固定。报告[交战门禁](docs/PHASE_06_PPO_ENGAGEMENT_GATE_MVP_REPORT.md)及[精简JSON](docs/validation/p6_ppo_engagement_gate_mvp.json)；来源artifacts/p6_engagement_gate_20261022/freeze SHAde4eb03773452447769e146c1bb79ea7221b88342d4f94a37487915cdc2c2022、evidence SHA9c69951bb5191a9fd443fad1e05a702181f115caacbe1734a9a92688e0934c97。原始工件/模型Git忽略迁移另带；待root最终本地保存、未push，后续游戏/训练需新预算。

## 2026-10-22 P4 多源冻结93条与单次BC候选

旧82条加既有专家subset11条一次导出新93条（train43/validation24/test26），仅新增一个dual_zergling_train组，无新双敌heldout；旧82前缀、validation/test六数组和来源顺序逐值不变。真实场景版本为v6。多源导出保留原接口，逐来源排除/契约/分组泄漏及重复引用审计，2个passed suite共历史25 runs、13个所选kite raw来源，非本轮新增游戏。

一次新BC沿用seed42/1000epochs/lr.003，validation选epoch1000后test一次：train/val100%，test仍23/26=88.46%、动作3召回仍.5；test loss由旧.4317181706升至.4963506460，未改善。旧val/test已历史使用，只作工程回归；不推双敌能力、泛化或收益，不promote。新模型NumpyBCPolicy加载、93条logits有限/动作合法且批量运行一致，最大logit差7.629e-6；23冻结文件hash未变，独立只读scope通过。同一合并fixture初版及补跨split raw覆盖后各1/1通过，未重跑全suite。

新数据 `artifacts/micro_datasets/p4_merged93_20261022` SHA `5e926766664d796f74f42e460d86703023cc07769c249eec7670d225ac6fa515`，新候选 `artifacts/models/marine_bc_merged93_20261022_seed42` weights SHA `7f100e471aa4086ddaf5ca006ea1f6e9c29bea8812d3088e1e8b2b71a8b9e16a`。默认BC仍旧82条，PPO仍curriculum256；新候选仅显式 `--bc-model artifacts/models/marine_bc_merged93_20261022_seed42` 选择（运行会启动游戏，本轮未执行）。原始工件Git忽略需另带；0新游戏/LLM/API/PPO训练、无自动切换，P4全面验收与训练就绪未建立。见[多源BC报告](docs/PHASE_04_MERGED_BC_MVP_REPORT.md)及[共享JSON](docs/validation/p4_merged_bc_mvp.json)；本轮待root本地保存、未push。


## 2026-10-22 P4 固定双BC新双敌heldout MVP

采前冻两BC weights/meta/trainreport+93数据/meta共8文件，本轮0训练/优化/epoch选择、SHA全同。只显式新增dual_zergling_validation/test，不扩默认24；两kite短case各1局、两独立suite passed/exit0，18.031+16.719=34.750墙秒，无retry/补局。名义距6+10(seed111)/9+10(seed121)，敌HP1/.5；实际val frame26距3.134765625/7.134765625、CD1.008789、首RETREAT2，test frame17距9/10、CD0首APPROACH3。两局均low_health_safety_exit截断未全杀，外层leave Defeat不当自然战败。

34raw→30eligible（val14→13/test20→17）；仅bothpass后四summary一次新导出123=93+13+17，split43/37/43，旧93六数组前缀及旧val24/test26原序不变。新val/test各对全部历史及彼此的float32 obs/obs+mask exact重复0（-0/+0同），资格true仅此无重叠门槛；历史自身crosssplit train–val/train–test/val–test仍4/1/1 matching pairs，两审计一致、保留。不同group不证明独立，两新case各1episode，不能把30行称30独立场景，旧val/test历史多用不重新称新heldout。

两固定BC均val13/13、test17/17且模型动作30/30一致；标签[1,3,6,0,3]/[0,6,7,3,1]，缺类recall=null。原82→93BC loss val .00104189385→.00080204115/test .00556176808→.01483467408，test更差、不推训练收益；规则专家未全杀，标签一致≠战力/学会1v2/强泛化。新NPZ SHA `8f711539428a4b58bb03715060726e34a5f8b0f0d7f8340352cf21eb598525dd`；freeze SHA `db4d429c69b6574ddd0a2e902f3e20c827d97b826e0a5d86014edaa04a5e70c9`，frozen_evaluation SHA `e9c162562016c881e59919f8e9d4efb699c0335bc9cb33c829ec0dbfeaf32051`。独立核心scope通过，4summary/15raw来源SHA匹配、8冻结文件同、SC2残留0；定向fixture初版及缺失case处理后各通过，未跑历史全suite。

见[固定双BC报告](docs/PHASE_04_DUAL_HELDOUT_MVP_REPORT.md)及[精简JSON](docs/validation/p4_dual_heldout_mvp.json)，原始证据 `artifacts/p4_dual_holdout_20261022`、新dataset同名；工件Git忽略迁移另带。默认BC82/PPO256及guard/交战门禁不改，动作奖励不改、不promote；无LLM/API/PPO训练/额外游戏/安装。P4千条、训练就绪及P4/P5/P6全面验收未建立；后续训练/游戏需新预算。本轮待root本地保存、未push。
