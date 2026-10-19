# P6 E0–E4 离线评估矩阵 MVP

仅汇总指定历史工件，不运行SC2、API或训练。系统可运行证据与正式强度比较分别判断；本报告不构成正式P6验收或模式胜率优势。

| 模式 | 证据 | attempts | 完整已知结果 | failed | 整场truncated | unknown状态 | 胜/负/平 | 未知结果 |
|---|---|---:|---:|---:|---:|---:|---|---:|
| E0 Rule/Rule | missing | 0 | 0 | 0 | 0 | 0 | 0/0/0 | 0 |
| E1 LLM/Rule | missing | 0 | 0 | 0 | 0 | 0 | 0/0/0 | 0 |
| E2 Rule/BC | missing | 0 | 0 | 0 | 0 | 0 | 0/0/0 | 0 |
| E3 Rule/PPO | present | 1 | 1 | 0 | 0 | 0 | 1/0/0 | 0 |
| E4 LLM/PPO | present | 2 | 1 | 1 | 0 | 0 | 1/0/0 | 1 |

attempt分母保留全部输入；unknown不记负或胜。JSON中的已知结果胜率/Wilson区间仅描述所选记录，端到端Victory比例使用全部attempt分母；两者不能相互替代。missing模式的比率为null。

| run | 状态 | 结果 | LLM预算/采用步 | PPO推理/owned | 局部micro截断 |
|---|---|---|---|---|---:|
| `e3_fullmatch_ppo_20261019` | completed | win | 0/None | 233/233 | 54 |
| `e4_fullmatch_llm_ppo_20261019` | crashed | unknown | 20/231 | 110/110 | 22 |
| `e4_fullmatch_llm_ppo_20261019_snapshotfix` | completed | win | 16/428 | 240/240 | 71 |

公平配置包含地图及SHA、对手、难度、实时/步进、seed、时限、控数、Ares/packages、共享执行器源码与game build。模式、模式适配源码、actor SHA、LLM模型/预算/请求日期单列；不会因为Rule/LLM或Rule/PPO的预期差异直接拒绝跨模式匹配，也不按模型路径斜杠判身份。缺失字段不会默认相等。

当前各run缺失项：
- `e3_fullmatch_ppo_20261019`: game_build。
- `e4_fullmatch_llm_ppo_20261019`: game_build, llm_model。
- `e4_fullmatch_llm_ppo_20261019_snapshotfix`: game_build, llm_model。

观测到的共享配置差异：shared_source_hashes。详见JSON逐run配置与源SHA。即使配置完整相同，也须预冻结评估轮次、交叉顺序、多地图/种子及独立训练种子，不能从当前记录自动推导正式比较资格。

失败attempt始终计入端到端分母，必要修复后的成功不消除首次失败。不同源码/预算或配置单局不能拼接成模式强度结论。原始artifact不修改；JSON保留读取文件SHA、project commit和工作树diff身份。LLM预算与实际采用不是同一指标；局部micro截断不代表整场截断。

复现（run ID在artifacts/runs下；自定义目录输入时替换为原目录）：

```powershell
python -s tools/report_evaluation_matrix.py "e3_fullmatch_ppo_20261019" "e4_fullmatch_llm_ppo_20261019" "e4_fullmatch_llm_ppo_20261019_snapshotfix" --output docs/validation/p6_evaluation_matrix_mvp.json --markdown docs/PHASE_06_EVALUATION_MATRIX_MVP_REPORT.md
```
