# P6剩余E1/E3/E4固定配置工程MVP

2026-10-20；基于HEAD `88206e9c22798d3de1bcaf8c6a9f8d664ff71de4`，没有源码/模型/依赖变更、训练、外部模型开发代理或额外游戏测试。唯一新批`p6_runner_e1e3e4_20261020`按预冻结清单仅E1、E3、E4各1局，均自然官方Victory、exit0、保存回放。实际战略逻辑请求11（E1=5、E4=6）≤20，预分配10/0/10且未用额度未转移；全部11响应HTTP200/有效并激活，无在途请求遗留。它是三条组合运行链路证据，不证明强度、可推广胜率或训练收益。

## 预算、冻结和唯一执行

固定Ancient Cistern LE、Zerg Easy、非实时8loops、seed20261020、最多4名Marine、1200游戏秒/600每局墙秒。与旧E0/E2的common、game_path、安装地图、Ares commit、Python路径/版本及两plan全部240项source_hashes相同；旧冻结revision为`9f896dee0b640db9bb4d2a4dfbd58ff62b32050c`，新为`88206e9…`，属于两个独立冻结plan，不声称同完整源码快照或同一评估轮次。两批PPO不能作身份对比：旧批只有BC；新E3/E4使用同一个curriculum256 actor。

仓库根目录实际执行（这些目录已存在；不要重建覆盖）：

```powershell
& C:\Users\27932\anaconda3\envs\sc2-ares-runtime\python.exe -s tools/run_evaluation_matrix.py --batch-dir artifacts/evaluation_batches/p6_runner_e1e3e4_20261020 --modes E1 E3 E4 --llm-max-calls 20 --game-path 'C:\Program Files (x86)\StarCraft II' --ppo-model artifacts/models/marine_ppo_curriculum256_20261019
& C:\Users\27932\anaconda3\envs\sc2-ares-runtime\python.exe -s tools/run_evaluation_matrix.py --resume artifacts/evaluation_batches/p6_runner_e1e3e4_20261020 --execute
```

首命令dryrun exit0/0游戏；唯一execute顺序启动3局，无失败重试或补局。全终态后同resume命令仅再运行一次exit0/0.375秒，全部attempt起止时间/PID/结果未变，0新增局；源码、模型、地图身份经runner复核通过。两层锁均移除，SC2_x64查询无残留。局中只读追加日志/事件，未读live latest_state，也未查看凭据文件。

plan规范化SHA256 `fa0c21372c9f10c7c24ad2aa9f48cd182c2b45534ee9d82bf9af24388fcdc298`。安装地图SHA `13d075a466de88ba93aa3d9f3e9f3743606bffac1bf1b5e81f42b0c56d4a9c59`；PPO weights SHA `8a0e810b5e686fd71fa74f4a7f7b5be486401647b3119b4ec7bd87e1a94bbfc1`。完整plan、state、每局summary/events/raw/回放/log SHA及resume结果均在[共享JSON](validation/p6_remaining_modes_mvp.json)；原始batch/run/model Git忽略，迁移须另带。

## 新批全部attempt

| 模式 | run ID | 终态/官方结果 | 游戏秒 | runner墙秒 | 实际请求/分配cap | PPO推理/owned/transition |
|---|---|---|---:|---:|---:|---:|
| E1 | `p6_runner_e1e3e4_20261020_E1` | completed/Victory | 365.000000 | 39.391 | 5/10 | 0 |
| E3 | `p6_runner_e1e3e4_20261020_E3` | completed/Victory | 360.357143 | 36.672 | 0/0 | 220 |
| E4 | `p6_runner_e1e3e4_20261020_E4` | completed/Victory | 395.714286 | 40.360 | 6/10 | 203 |

三局summary.error=null、command_conflicts=0；三份终态launcher日志ERROR/Traceback/Exception扫描0。E3/E4均有ppo_model_loaded事件、无模型fallback事件。生产低HP、敌种/静态防御和控数保护下规则接管不等于模型失败fallback；逐原因次数和实际敌type分布未记录，不臆推。

E1：5请求/5HTTP200/5valid active，402 LLM步=402经济目标步、316军队目标步，223等待callbacks。E4：6请求/6HTTP200/6valid active，434 LLM步=434经济目标步、372军队目标步，263等待callbacks。后台API保持非阻塞；HTTP200与实际目标采用分别有计数，不能把请求数当采用步数。

E3的220真实transition/28tags，动作0..4=[0,5,123,14,78]，134 engine_confirmed+78 hold+4 order_preserved+4 engine_unconfirmed。E4的203真实transition/24tags，动作[0,8,92,41,62]，132 confirmed+62 hold+1 preserved+8 unconfirmed。423条全部8loops/mask合法；hold可延续自动攻击，preserved/unconfirmed不冒充新增引擎确认。局部truncated E3=77、E4=50是微操ownership释放，不是整场比赛截断。

E4按events文件顺序、最近strategy_source=llm区间统计：43条PPO owned micro_command事件、14个owned微步、11个Marine tags与LLM实际激活重叠；事件含hold等，不全是新下发命令。

全部423行原始split=train，但versions.expert=null、bc_eligible=false、reward=null/not_implemented；仅新增各run的learning_exclusion.json，按rawSHA永久排除未来训练，不修改raw、不导出训练数据。模型仍为单体课程actor，最多4名Marine逐个共享，不是训练过的群体策略；未记录敌种分布，不能排除课程外支持敌种。

## 与旧E0/E2衔接及历史失败

固定描述性5run清单仅为下表，不代表所有历史尝试；完整配置和比较缺项见共享JSON的fixed_five_inventory。旧E0/E2证据参见[runner报告](PHASE_06_MATRIX_RUNNER_MVP_REPORT.md)。

| 模式 | 选择的run ID | 工程结果 |
|---|---|---|
| E0 | p6_runner_e0e2_20261020_E0 | completed/Victory |
| E1 | p6_runner_e1e3e4_20261020_E1 | completed/Victory |
| E2 | p6_runner_e0e2_20261020_E2 | completed/Victory |
| E3 | p6_runner_e1e3e4_20261020_E3 | completed/Victory |
| E4 | p6_runner_e1e3e4_20261020_E4 | completed/Victory |

这个限定集合现5模式各1完整局，仅说明所选工程运行链路均完成。旧E4首局`e4_fullmatch_llm_ppo_20261019`仍是crashed/unknown（latest_state可选快照替换WinError5），不能从历史分母删除；其失败及唯一修复重验保留在[原E4报告](PHASE_06_E4_FULLMATCH_MVP_REPORT.md)和[原3attempt矩阵](validation/p6_evaluation_matrix_mvp.json)，原E4完整1/2、原3attempt完整2/3仍成立。本次固定5run清单不包含那轮历史，不能写“所有历史5/5”。本轮没有失败重试，也没有改旧artifact或旧报告。

全部5run原始manifest仍缺game_build；E1/E4 request遥测另缺LLM模型标识。既有DeepSeek私密loader可用不补足模型身份，远端行为/模型版本及完整引擎初态未冻结。两批分别冻结、单seed、每模式n=1，未做交叉顺序/多地图/独立种子，不能据结束时间或余兵排序强弱。formal_comparison_ready=false；正式P6验收、P5全面验收及训练budget-close EOFError历史缺口仍未完成。

下一步需新授权预算后记录build/LLM模型身份与完整评估设计，再少量独立seed；不自动追加游戏，不把本工程样本升级为收益结论。
