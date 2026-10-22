# P4 多源冻结93条与单次BC候选 MVP

2026-10-22，基于 HEAD `5fe5c1beecff2b600de508ba6ec7625676e97fb2` 加本轮多源导出补丁。只合并既有两个规则专家summary、训练一个新候选，没有新增游戏或LLM/API请求。旧82条、旧模型和默认入口保留。

## 来源与冻结

`tools/export_micro_dataset.py` 保留原单summary API/CLI，新增可重复 `--additional-summary`。每来源检查学习排除sidecar、技术合格标签及契约，拒绝跨split group/raw泄漏；重复来源引用去重并保留审计。metadata.source_suites保留全部来源分母和SHA，而不是只列入选kite。旧suite24 runs/12 kite，新subset1 run/1 kite；总25个历史run，13个所选raw来源（含旧空raw），不是本轮新增25局。

一次导出将旧82条与新增11条合成 `artifacts/micro_datasets/p4_merged93_20261022`，train43 / validation24 / test26，动作0..4为[4,19,27,9,34]，重复引用0。旧82条为逐值相同前缀，旧validation/test的obs、mask、action、game_loop、group、split数组及旧来源身份顺序逐值不变。实际契约marine-16-v1 / marine-5-v1 / 8loops，专家marine-kite-v1，场景marine-vs-marine-v6及marine-vs-zergling-v6；目录v7不代表场景v7。

新增11条仅来自一个dual_zergling_train group，动作[0,2,2,0,7]，缺动作0/3；没有新双敌validation/test。该历史case低血安全截断、未全杀，不能写成1v2能力通过；局部结果见[subset报告](PHASE_04_EXPERT_SUBSET_MVP_REPORT.md)。旧validation/test历史已多次使用，本轮仅工程回归，并非新独立heldout。

| 工件 | SHA256 |
|---|---|
| 旧summary | `7359e6d41d50b83728e037b869198b09451d6184678f610adcaf70398245ffb0` |
| 新summary | `593732cec73e295077c4901e9600652425fb02f0408ef9ea46505d4f38fc129c` |
| 新93条NPZ | `5e926766664d796f74f42e460d86703023cc07769c249eec7670d225ac6fa515` |
| 新metadata | `3ca1ebd25219496c2ca8b1207d1acb4ca3f1e3e5ea74002b718757bde86f0dd2` |
| 旧82条NPZ | `6558232fea2386e1bef792b50e728b7f5e13ff6a47498837538dd4b0f91aee9e` |
| 旧BC weights | `e36cba313c1d8e1731573595b1b975316e1522db3af8d1a4abf4f21e405c2dcf` |
| 新BC weights | `7f100e471aa4086ddaf5ca006ea1f6e9c29bea8812d3088e1e8b2b71a8b9e16a` |

## 单次训练与结果

新目录 `artifacts/models/marine_bc_merged93_20261022_seed42`。沿用NumPy 16→64→64→5/Tanh、seed42、1000 epochs、lr0.003；只优化train，以validation最小masked loss选epoch1000，随后test一次，没有据test重训或调参。此候选从本轮数据训练，旧BC仅为比较基线、没有加载其权重续训。

| split | 条数 | masked loss | masked准确率 |
|---|---:|---:|---:|
| train | 43 | 0.0001298771 | 100% |
| validation | 24 | 0.0001933201 | 100% |
| test | 26 | 0.4963506460 | 88.46%（23/26） |

旧test loss为0.4317181706，新候选增加0.0646324754；test准确率仍23/26，动作3召回仍50%，其余100%。loss变差，没有准确率提升，不能据此宣称模型质量、双敌强度或学习收益提高。prototype=true、training_readiness=not_established；P4千条及更广边界一致性验收尚未完成。

## 最小核验与使用

同一合并fixture初版1/1通过，补跨split同raw覆盖后该项再1/1通过；没有重跑全suite。新NumpyBCPolicy真实加载，93条既有样本logits有限、动作合法，trainer/runtime动作全部一致，最大logit绝对差7.62939453125e-6；全部23个preflight冻结文件hash前后一致（包括旧数据、旧模型、来源和相关源码）。离线核验未启动游戏，不计新真实部署或战斗验证。

导出和训练各执行一次；原始核验在 `artifacts/bc93_preflight_20261022.json`、dataset的 `pretrain_verification.json`、model的 `artifact_verification.json`。精简共享证据见[JSON](validation/p4_merged_bc_mvp.json)。工件Git忽略，迁移需另带。

`run_bc.cmd`默认仍旧82条BC；只有显式 `--bc-model artifacts/models/marine_bc_merged93_20261022_seed42` 才选择新候选，该运行命令会启动游戏，本轮未执行。默认规则、PPO curriculum256、guard和交战门禁默认设置均未切换。无自动promote、额外游戏、PPO训练、安装或凭据读取；本轮待最终本地保存、未push。
