# P3 后续：固定场景对照、数据冻结与新机LLM恢复

2026-10-14。延续开发规划第8节；本轮保持marine-16-v1 / marine-5-v1 / marine-kite-v1，扩展场景生成和独立A-move对照。尚未训练BC/PPO，不宣称拉扯或LLM提高胜率。

## 本机LLM配置

用户提供的配置已写入Git忽略的 `.env.local`，base为DeepSeek官方HTTPS端点，model=deepseek-flash。密钥不进入命令行、源码、汇总或提交。规则/场景采集不调用远端LLM。

`llm_restore_shadow_2`：45游戏秒实时影子测试，2请求/2响应/2合法计划，延迟1.235/0.890秒；请求等待期间48次游戏回调，结束无请求在途。状态truncated，比例0.98114；只证明提供方配置及非阻塞链路恢复，影子模式没有实际接管。

`llm_restore_full_cap20`：完整实时Victory，20请求/20响应/20合法计划；LLM实际控制7541个回调，经济目标7541步、军队目标647步，等待期间545次回调。调用上限20达到后不再请求，旧计划过期回规则；规则共1928回调，结束没有请求在途。游戏422.679秒/活跃wall430.747秒，比例0.98127；on_step p95 1.680ms、最大6.553ms；0异常/0命令冲突，工人43/Marine63/基地2峰值。该局验证真实接管与预算回退，不代表全局一直由LLM控制或胜率改进。共享汇总在 `docs/validation/llm_new_machine.json`，原始日志和回放保留在artifacts。

用户现在可直接使用 `run_llm.cmd`；默认请求上限仍是原来的60，本次20仅是明确的验证参数。微操数据仍单独采用固定规则战略，不将本局混入学习微操的训练数据。

## 场景与专家

`tools/run_micro_scenario.py` 新增距离3/6/10、己方/敌方初始生命比例、kite/amove、显式数据split和潜地敌方诊断。出生点离双方公开起始位置至少25单位，排除已有宏观单位/基地附近区域。地形空地检查覆盖战斗线及3单位余量；出生区域不足时明确记录system_failure，不偷偷选择另一个参数。

血量通过SC2调试协议在采集前设置，等待可见敌人完成初始化也受游戏时间上限约束。`initial_scene_observation.json`记录真实初始位置、生命和可见敌人数；不可见性以引擎观测为准。

原生A-move通过既有规则命令钩子和arbiter向场景目标点下令，不采用拉扯。原生点攻击不能伪装成本项目“攻击某单位”的离散标签，因此它只用于结果对照，不生成BC标签。两种专家各自的完整SC2比赛都在局部结果或时间上限后主动截断，SC2的Defeat不算局部战术负场。

`tools/evaluate_micro.py` 在运行前冻结8个case：满血Zergling近/中距离、满血Marine近/中距离、己方半血对两种敌人、潜地不可见、极短时间上限。每个case串行执行amove/kite，各case的地图/种子/血量/距离和split相同，不跨训练与测试；不同case安排train/validation/test。每个子进程120实际秒watchdog只清理自己创建的进程树。每局保存源码、配置、回放和审计结果，源码变动拒绝继续混入。

```bat
conda activate sc2-ares-runtime
cd /d C:\code\SC2Agent_llm
python -s tools/evaluate_micro.py
python -s tools/export_micro_dataset.py artifacts/micro_suites/<suite_id>/summary.json artifacts/datasets/<dataset_id>
```

导出器仅接受完整passed批次和未经修改的已审计输入，排除amove、未确认/拒绝/重复抑制/截断/非8帧样本。NPZ含float32观测、bool掩码、int64动作、帧和分组/split字符串，可用allow_pickle=False读取；metadata记录输入与数据集SHA256、动作与split分布、缺失动作。技术筛选通过不等于数据覆盖足够训练。

## 最终场景批次与数据

`p3_coverage_v4`：16/16运行通过工程检查，0未处理异常/命令冲突。A-move与kite各为2次敌人死亡、4次低血量安全退出、2次时间上限；本轮结果分布相同，没有专家收益结论。潜地case两种专家的真实初始观测均为0可见敌人、0微操标签，正常限时退出；极短case验证截断关闭记录。

冻结数据为 `artifacts/datasets/marine_coverage_v4/demonstrations.npz`，共54条：train20、validation19、test15；动作1/2/3/4分别11/16/5/22，动作0缺失。全体样本包含训练、验证、测试分组，但54条和缺失动作不足以支持启动正式BC。数据摘要见 `docs/validation/micro_dataset_v4.json`，批次证据见 `micro_coverage_v4.json`。44项单测、格式与凭据泄漏检查通过。

## 失败保留与剩余限制

早期coverage_v2/v3在“距离10即不可见”的用例断言处失败：真实游戏可见敌人，策略对其下令合法，测试前提错误。v3同时加入远离基地条件后仍可见，故不能仅将原因归于基地视野。距离16的尝试找不到支持的同高度空地，记为system_failure。最终用真实潜地敌方替代距离猜测，并保留上述失败目录和日志，不将失败批次导出训练。

固定1v1的最低生命与最近目标常常相同，动作0示范可能缺失；需补2目标场景与更广的地图/距离/血量、实际死亡等覆盖，再判断BC输入是否足够。奖励仍为null，Gym reset/step与PPO桥接未实现。短场景对照只作为工程证据，正式算法收益需冻结场景集和多训练种子。
