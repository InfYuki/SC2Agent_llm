# 真人 Terran 对练与赛后学习入口

2026-10-22。新增 `run_human_training.cmd`，将已有 LLM+PPO 组合接入本地 Human versus Bot；人类玩家为 Terran，Agent 同样为 Terran。用户在 HumanTerran 窗口操作，LLM_PPO_Training 窗口由 Agent 控制。启动脚本自动定位运行环境、预检独立训练环境，实时运行一局并自动处理赛后学习，无默认对局时间上限。

```bat
cd /d C:\code\SC2Agent_llm
run_human_training.cmd --show-config
run_human_training.cmd --check-only
run_human_training.cmd
```

## 两条学习路径

LLM：读取已有私密DeepSeek配置，单局最多240次请求。记录可见状态、接受的计划及比赛结果；自然终局后更新跨局经验，下一局将有界经验加入战略快照。这里的学习为提示上下文记忆，非远端模型权重微调，历史经验也不是当前敌军情报。

PPO：初始采用现有448 actor与配套checkpoint，训练局使用随机合法动作采样并保存行为log probability。记录本地可见敌人HP损失、己方HP损失及确认死亡，形成有限微操奖励；不把消失在迷雾的敌人当作击杀。赛后校验行为checkpoint/actor/概率一致，按每名Marine的ownership片段计算GAE，使用实际帧间隔折扣、死亡零bootstrap、非终止边界价值bootstrap，执行少量masked clipped PPO更新。requested动作作为行为动作，执行保留旧命令等结果另记，不把两者概率混用。

成功后保存actor/critic/优化器checkpoint，导出NumPy actor并发布成对最新指针。下次真人入口自动加载，普通官方Bot入口不自动切换到真人训练模型。LLM与PPO独立报告状态；不足8条有效样本明确跳过PPO。失败保持原最新指针，不重复消费已经更新的PPO轨迹。自然完成且来源合格的对局才学习，错误/中断/时间截断保留诊断但不训练。旧评估数据永久禁训规则不变。

## 工件与使用边界

- 每局：`artifacts/runs/<run_id>/game.SC2Replay`、`events.jsonl`、`summary.json`、`human_training.json`、`human_ppo_rollout.jsonl`、`micro_transitions.jsonl`、`learning_report.json`、`learning/`。
- 跨局：`artifacts/human_training/memory/strategy_memory.json` 与 `ppo_latest.json`；最近启动日志为 `artifacts/last-human-run.log`。
- 覆盖解释器：`--training-python PATH` 或 `SC2_TRAINING_PYTHON`；自选模型成对指定 `--checkpoint PATH --actor DIR`。
- 人类在游戏内正常结束或认输后等待终端赛后学习完成；直接关客户端/终端可能只留下失败诊断。

当前仅支持最多4名Marine共享单体微操actor。Terran Marine接战可产生学习样本；坦克、空军、静态防御等超出当前特征/动作接口的场面由规则处理。运营与其他部队执行仍在现有Ares/规则范围。LLM仅能调整已实现的Marine经济和主力任务，尚非完整科技树指挥。

## 本轮验证

启动配置预检、依赖/私密配置安全预检与Python编译检查通过；4项运行接口定向检查覆盖真人采样实际帧间隔、缺失端点剔除、双客户端终局/回放及自有清理、学习身份覆盖拒绝与既有LLM+PPO组合兼容。独立训练环境1项检查用8条合成采样进行了真实参数更新、导出与成对最新指针验证，并检查重复消费拒绝、行为概率篡改拒绝和失败时旧指针保持。该离线检查不启动SC2、不调用API，合成数据不是用户真人训练资料。本轮没有实际真人参与对局，因此双窗口操作、真人终局与真实对局更新仍需首次使用确认，不声称已经实机验证完整真人训练链路。
