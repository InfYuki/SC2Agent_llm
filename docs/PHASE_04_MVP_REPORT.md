# P4 BC 快速工程原型

日期：2026-10-18。目标是尽快得到可加载、可运行、失败能回退的BC原型；保留P3冻结数据和历史报告，不扩大采集或重复24局suite。

## 训练与产物

使用已冻结82条技术合格样本，train32 / validation24 / test26，分组不变。NumPy MLP 16→64→64→5，隐藏层Tanh，masked交叉熵与Adam（lr=0.003、seed42、1000 epochs）。仅train参与优化，validation最小masked loss选择epoch1000，选定后最后评估test一次；没有安装Torch或PPO训练栈。

| split | 条数 | masked loss | masked准确率 |
|---|---:|---:|---:|
| train | 32 | 0.00013841 | 100% |
| validation | 24 | 0.00036366 | 100% |
| test | 26 | 0.43171817 | 88.46%（23/26） |

测试集动作3召回率50%（3/6），其余动作召回率100%。这是标签一致性，不能解释成战斗强度或泛化；82条及独立几何覆盖仍不足，`prototype=true`、`training_readiness=not_established`。

本机产物：`artifacts/models/marine_bc_mvp_20261018_seed42/{weights.npz,metadata.json,training_report.json}`。权重SHA256为 `e36cba313c1d8e1731573595b1b975316e1522db3af8d1a4abf4f21e405c2dcf`；数据SHA256为 `6558232fea2386e1bef792b50e728b7f5e13ff6a47498837538dd4b0f91aee9e`。模型和原始数据被Git忽略；共享摘要为 [micro_bc_mvp.json](validation/micro_bc_mvp.json)。

## 使用与回退

[README_LOCAL.md](../README_LOCAL.md) 提供可复制PowerShell命令：完整本地入口 `run_bc.cmd`（`--mode rule_bc`），默认以脚本目录定位本次模型，可传 `--bc-model <模型目录>` 覆盖，诊断场景 `tools/run_micro_scenario.py --policy bc --bc-model <模型目录>`。默认规则入口不变；运行不调用LLM。启动脚本默认路径和参数覆盖仅做CLI静态核对，未增加游戏测试。

加载时校验契约、形状、float32、有限数和权重哈希。加载或推理失败记录原因并转规则，当帧mask、唯一arbiter出口、低血量保护继续生效。BC及其规则回退数据标记 `policy=marine-bc-numpy-v1`、`expert=null`、`bc_eligible=false`，不作为规则专家示范。

## 最小验证

新增6项必要定向测试通过（训练2、运行4），CLI与diff检查通过；本轮没有重跑历史58项或24局采集suite。82条真实冻结样本trainer批量/runtime逐行logits最大绝对差5.7220458984375e-6（allclose容差1e-5），82个masked动作全部一致、非法0。规划至少1000条真实及边界特征尚未执行，因此本轮仅可用MVP，未正式P4验收。

| run_id（20游戏秒上限） | 决策 | 局部结果 |
|---|---|---|
| p4_bc_mvp_smoke_20261018 | 14 BC推理 / 14 owned | enemy_dead，5.804秒 |
| p4_bc_missing_smoke_20261018 | 1次FileNotFoundError加载回退，14规则决策 / 14 owned | enemy_dead，5.848秒 |

两局各exit0、error=null、命令冲突0、非法mask动作0、engine error0；各4 engine_confirmed + 10 HOLD。合计28条记录全部expert=null、BC policy、bc_eligible=false。两局相同局部结果不证明BC优于规则。外层完整match主动截断，summary沿用game_time_limit及Result.Defeat分类；局部结果读scenario_result，不能写成全局获胜或胜率。

原始汇总：artifacts/bc_validation/p4_mvp_20261018_1232/verification_report.json；共享JSON包含训练摘要、原始验证结果和上下文。

## 后续

按用户快推进偏好，下轮先做P5单Marine Discrete(5)的reset/step/action_masks/close、局部生命损失差奖励、terminated/truncated与worker清理。先stub契约，再接真实SC2步进；stub不能冒充可训练环境。规划§10.1为独立工作包，§15允许明确独立PPO基线，无需先BC→PPO迁移。实际PPO训练前仍需真实桥接、清理与吞吐验收。PPO的Gym reset/step桥接、更多敌种/地形/死亡边界及战斗收益比较均未完成；P3局部停止summary分类限制仍按历史报告处理。
