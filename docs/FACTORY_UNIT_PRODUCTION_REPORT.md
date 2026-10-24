# Factory 全兵种生产链与基础控制

日期：2026-10-24。当前目标仍是战胜用户本人。

## 范围与依赖

标准对战 Factory 六种单位现纳入本轮范围：Hellion、Hellbat（SDK 名 `HELLIONTANK`）、Widow Mine、Cyclone、Siege Tank、Thor。变形状态不作为额外生产兵种。

| 单位 | 本机 SDK / Ares 科技依赖 |
|---|---|
| Hellion | Barracks → Factory |
| Widow Mine | Barracks → Factory |
| Hellbat | Factory + Armory；可直接训练，也可由 Hellion 转换 |
| Cyclone | Factory + 已附着的 Tech Lab |
| Siege Tank | Factory + 已附着的 Tech Lab |
| Thor | Factory + 已附着的 Tech Lab + Armory |

生产依赖以本机锁定的 `sc2.dicts.unit_train_build_abilities.TRAIN_INFO` 及 `ares.dicts.unit_tech_requirement.UNIT_TECH_REQUIREMENT` 为准。Cyclone 历史版本曾有不同科技要求，不能套用旧版本攻略。官方背景参考：[Blizzard 5.0.14 PTR 更新](https://news.blizzard.com/en-us/article/24150098/starcraft-ii-5-0-14-ptr-patch-notes)，不据此推断本机未查询的即时单位数值。

## 验证与边界

本轮只做离线定向检查和代码审查，未新开 SC2 对局、调用 LLM API 或更新训练模型。Marine PPO 的16维观测／5动作接口不变，其他单位由规则控制。真人入口和赛后人工学习确认流程保持不变。

任务收尾只清理本轮临时文件和安全源码缓存；保留训练产物、回放、学习记录、依赖、证据与正式报告，不重新尝试上轮自动审批拒绝的三项残留。

## LLM 可选编成与控制

- `factory_hellion_cyclone`：Marine 25% / Hellion 35% / Cyclone 40%。
- `factory_mine_tank`：Marine 40% / Widow Mine 25% / Siege Tank 35%。
- `factory_thor_hellbat`：Marine 20% / Hellbat 50% / Thor 30%。

比例为单位数量目标，不是资源占比或保证每一时刻精确满足。原五种编成及旧策略仍合法，默认混编不变。Factory 首次科技与单位费用来自运行时游戏数据，避免硬编码历史 Cyclone 费用；工人、供给与安全扩张仍优先。

Hellion / Hellbat 基础移动与攻击，选择相应编成时按需转换；Widow Mine 对附近可见地面或空中敌人下埋，停留期间不发无效移动／攻击覆盖自动开火，安静后收起转场；Thor 两种形态始终受规则控制，可按近处可见空军的类型调整武器模式。Tank 原架起／收起逻辑保留。Cyclone 可基础攻击，暂不含 Lock On 通道与风筝控制。所有变形中的单位不被普通移动命令反复打断。

## 定向检查

Factory／兵营／Tank-Medivac／Stim／经济／策略／LLM-PPO 的组合检查最终20项通过。新增实际控制集成覆盖 Hellion 转 Hellbat、空军触发 Widow Mine 下埋、下埋状态不发普通攻击、安静后收起、Thor 对可见重型空军切换武器并攻击，以及保留 Marine 已发命令与所有权。

Hellion 与 Hellbat 不属于 Ares 的自动同类计数，生产计划在现存免费转换完成前短暂暂停后续生产，避免重复直产；工人、供给、安全扩张与采气保持在前。Tank、Thor 与 Widow Mine 的变形态由 Ares alias 计数，不因切换形态被误认为单位缺失。

最终代码审查核对附着 Tech Lab、Armory、首批单位资源储备、非 Marine 的规则控制及 Marine PPO 隔离。未用新增对局或远端 API 验证，下一场真人对练仍需观察新编成实际表现。

任务最终收尾已清理4处项目源码缓存，共37文件、410,089字节；未删除模型、回放、训练／学习记录、依赖或复盘审计证据，未重试以前被自动审批拒绝的残留。私密配置检查一次通过，源码及暂存白名单检查通过，本轮仅本地提交、不自动推送。
