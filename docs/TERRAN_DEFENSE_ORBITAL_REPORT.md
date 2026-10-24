# Missile Turret、Bunker 与 Orbital Command

日期：2026-10-24。当前目标仍为战胜用户本人。本轮补充静态防御、驻防与轨道经济能力，不新增对局或自动批准学习。

## 本机科技与执行接口

| 建筑／升级 | 本机 SDK / Ares 依赖 |
|---|---|
| Missile Turret | Engineering Bay |
| Bunker | Barracks |
| Orbital Command | 已完成 Barracks；由 ready、idle Command Center 升级 |

Ares `BuildStructure` 提供 Turret／Bunker 预设防御位置；`UpgradeCCs` 支持轨道升级。精确条件以本机锁定的 SDK 和 Ares 为准。Orbital 属于原有基地的升级，不应计成新扩张；MULE 不计入 SCV 补充目标。

## 策略与基础控制

LLM 增加 `base_defense: "none" | "standard" | "fortified"` 和 `orbital_command: true | false`。旧 strategy-v1 没有这两个字段时分别补为 `standard`、`true`，旧生产编成和 Stim 选择仍合法；两项变化进入策略 intent，而不是只显示在提示词里。LLM 快照包含当前防御策略、建筑数量和轨道开关。

- `standard`：前沿基地补一个 Bunker，每座成熟采矿基地补一个 Turret；`fortified` 允许两个前沿基地各一个 Bunker、每基地两个 Turret。先满足工人、供给和安全扩张；扩张储备期间不新增防御，防御不会永久锁住生产。Turret 不被宣称能独自击败 Battlecruiser 编队。
- Bunker 使用 Ares 的防御位置；附近 Marine 可装载，安全转场时卸载。装载前结束旧 PPO 轨迹，候选退出采样，不用原 PPO 的某个动作冒充装载。装载、卸载和技能发令计数均为本地指令记录，不是逐条引擎成功确认。
- Orbital 升级放在 SCV 排队前，避免 Command Center 永远没有空闲窗口；只允许一次一个，缺矿储备有8秒窗口／45秒重试，避免无限期停止补工人。
- Orbital 使用 MULE 辅助本方采矿，Scan 只响应本局已观察到的隐形／埋地威胁；不会读取回放中的全图信息，也不进行全图盲扫。既有 Orbital 即使后续关闭升级开关也继续使用技能。

这是一版有限的基地防御与轨道控制，暂不含 Bunker salvage／维修指挥、Supply Drop、普遍地图侦察或 Planetary Fortress 路线。

## 兼容与验证边界

Marine PPO 的16维／5动作接口保持不变；驻防、轨道技能和建筑由规则控制。载入 Bunker 不得新增伪 PPO 动作或判作死亡。赛后仍只有显式 Y 才更新经验或模型。

本轮仅定向检查与独立源码审查，未打开 SC2、调用 LLM API 或训练模型；建造布局、进出 Bunker 和 Orbital 技能仍待下一场实战观察。

实现代理的18项组合检查通过；新增检查覆盖旧策略缺字段兼容、轨道预算超时恢复补工人、pending轨道不重复升级、防御布局请求、Scan优先与保留能量、危险矿区不召唤MULE，以及实际 `MicroRuleBot.issue_combat_orders` 的“关闭旧轨迹 → 不采样 → 授权装载”单指令顺序。最终审查未重复运行这些检查。LLM快照的 pending bases 固定按 Command Center 施工统计，避免第一个基地升级后误把 Orbital pending 当新扩张。

任务收尾按根目录 `AGENTS.md` 清理本轮临时产物和安全源码缓存，保留模型、回放、学习记录、依赖和正式证据；不重试此前自动审批拒绝的三项历史临时残留。

最终源码／暂存白名单与差异检查通过，私密配置安全检查一次通过。定向检查后的缓存清理移除4个目录、35个文件，共400,616字节；最终安全白名单预览为零。仅保存本地提交，不自动推送。
