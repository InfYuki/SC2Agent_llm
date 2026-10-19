"""Offline E0--E4 evidence inventory; never launches games or loads models."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODES = {"rule": ("E0", "Rule/Rule"), "llm": ("E1", "LLM/Rule"),
         "rule_bc": ("E2", "Rule/BC"), "rule_ppo": ("E3", "Rule/PPO"),
         "llm_ppo": ("E4", "LLM/PPO")}
FAIR_FIELDS = ("map", "opponent", "difficulty", "realtime", "game_step",
               "seed", "max_game_seconds", "micro_max_units")
# Mode adapters, LLM code and actor identities are interventions, not shared knobs.
SHARED_SOURCES = ("config.yml", "poetry.lock", "bot/rule_bot.py", "bot/arbiter.py",
                  "bot/building_manager.py", "bot/compat.py", "bot/lifecycle.py",
                  "bot/telemetry.py", "bot/micro.py", "bot/micro_data.py")
FILES = ("manifest.json", "summary.json", "strategy_summary.json",
         "micro_summary.json", "events.jsonl")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def read_json(path, warnings):
    if not path.is_file():
        warnings.append(f"missing:{path.name}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("expected object")
        return value
    except (ValueError, OSError) as exc:
        warnings.append(f"unreadable:{path.name}:{type(exc).__name__}")
        return {}


def object_field(value, warnings, name):
    if isinstance(value, dict):
        return value
    warnings.append(f"invalid_object:{name}")
    return {}


def load_attempt(run):
    """Read fixed evidence filenames only; never follow model/config paths."""
    warnings = []
    manifest = read_json(run / "manifest.json", warnings)
    summary = read_json(run / "summary.json", warnings)
    config = object_field(manifest.get("config", {}), warnings, "manifest.config")
    sources = object_field(manifest.get("source_hashes", {}), warnings, "manifest.source_hashes")
    mode = config.get("mode")
    strategy = read_json(run / "strategy_summary.json", warnings) if mode in ("llm", "llm_ppo") else {}
    micro = read_json(run / "micro_summary.json", warnings) if mode in ("rule_bc", "rule_ppo", "llm_ppo") else {}
    identity = {"mode": mode, "llm_max_calls": config.get("llm_max_calls"),
                "project_commit": manifest.get("project_commit"),
                "dirty_diff_sha256": manifest.get("dirty_diff_sha256"),
                "actor_weights_sha256": None, "llm_model": None,
                "llm_request_date_utc": manifest.get("started_utc"),
                "mode_source_hashes": {k: v for k, v in sources.items()
                                       if k.startswith("bot/") and k not in SHARED_SOURCES}}
    events_path = run / "events.jsonl"
    if events_path.is_file():
        with events_path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                except ValueError:
                    warnings.append("malformed:event_line")
                    continue
                if not isinstance(event, dict):
                    warnings.append("invalid_object:event_line")
                    continue
                if event.get("event") in ("ppo_model_loaded", "bc_model_loaded"):
                    identity["actor_weights_sha256"] = event.get("weights_sha256")
                if event.get("event") == "llm_request" and event.get("model"):
                    identity["llm_model"] = event["model"]
    else:
        warnings.append("missing:events.jsonl")
    fair = {key: config.get(key) for key in FAIR_FIELDS}
    fair.update(map_sha256=manifest.get("map_sha256"),
                ares_commit=manifest.get("ares_commit"),
                game_build=manifest.get("game_build"),
                packages=manifest.get("packages"),
                shared_source_hashes={key: sources.get(key)
                                      for key in SHARED_SOURCES})
    missing = [key for key, value in fair.items() if value is None]
    missing += [f"source:{key}" for key, value in fair["shared_source_hashes"].items() if value is None]
    if identity["actor_weights_sha256"] is None and mode in ("rule_bc", "rule_ppo", "llm_ppo"):
        missing.append("actor_weights_sha256")
    if mode in ("llm", "llm_ppo") and identity["llm_model"] is None:
        missing.append("llm_model")
    status, result = summary.get("status"), summary.get("result")
    natural = status == "completed" and summary.get("error") is None and summary.get("stop_reason") is None
    outcome = {"Result.Victory": "win", "Result.Defeat": "loss", "Result.Tie": "tie"}.get(result, "unknown") if natural else "unknown"
    category = ("failed" if summary.get("error") or status in ("crashed", "failed", "system_failure")
                else "truncated" if status == "truncated" or summary.get("stop_reason")
                else "completed" if natural and outcome != "unknown" else "unknown")
    counters = object_field(summary.get("counters", {}), warnings, "summary.counters")
    strategy_counts = object_field(strategy.get("counters", {}), warnings, "strategy.counters")
    micro_counts = object_field(micro.get("counters", {}), warnings, "micro.counters")
    hashes = {name: hashlib.sha256((run / name).read_bytes()).hexdigest()
              for name in FILES if (run / name).is_file()}
    return dict(run_id=run.name, experiment=MODES.get(mode, ("unmapped", "unknown"))[0],
                fair_config=fair, identity=identity, missing_comparison_fields=missing,
                status=status, category=category, outcome=outcome, official_result=result,
                error_present=bool(summary.get("error")), stop_reason=summary.get("stop_reason"),
                evidence_sha256=hashes, warnings=warnings,
                engineering=dict(natural_known_result=category == "completed",
                                 replay_present=(run / "game.SC2Replay").is_file(),
                                 command_conflicts=counters.get("command_conflicts")),
                metrics=dict(game_seconds=summary.get("game_span_seconds"),
                             game_to_wall_ratio=summary.get("game_to_wall_ratio"),
                             llm_steps=strategy_counts.get("llm_steps"),
                             economy_goal_steps=strategy_counts.get("economy_goal_steps"),
                             combat_goal_steps=strategy_counts.get("combat_goal_steps"),
                             ppo_inference_decisions=counters.get("ppo_inference_decisions"),
                             micro_owned_decisions=counters.get("micro_owned_decisions"),
                             micro_transitions=micro_counts.get("transitions"),
                             local_micro_truncated=micro_counts.get("truncated")))


def wilson(wins, total):
    if not total:
        return None
    z = 1.95996398454
    p = wins / total
    scale = 1 + z * z / total
    center = (p + z * z / (2 * total)) / scale
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / scale
    return [center - radius, center + radius]


def counts(rows):
    categories = Counter(row["category"] for row in rows)
    outcomes = Counter(row["outcome"] for row in rows)
    n = len(rows)
    known = sum(outcomes[key] for key in ("win", "loss", "tie"))
    return dict(attempts=n, completed=categories["completed"], failed=categories["failed"],
                truncated=categories["truncated"], unknown=categories["unknown"],
                wins=outcomes["win"], losses=outcomes["loss"], ties=outcomes["tie"],
                unknown_results=outcomes["unknown"], known_result_denominator=known,
                descriptive_win_fraction_known=outcomes["win"] / known if known else None,
                descriptive_wilson_95_known=wilson(outcomes["win"], known),
                end_to_end_victory_fraction=outcomes["win"] / n if n else None,
                end_to_end_completion_fraction=categories["completed"] / n if n else None)


def build_report(paths):
    attempts, seen, duplicates = [], {}, []
    for path in paths:
        row = load_attempt(path)
        if row["run_id"] in seen:
            if seen[row["run_id"]] != path.resolve():
                raise ValueError("different input directories have the same run ID")
            duplicates.append(row["run_id"])
            continue
        seen[row["run_id"]] = path.resolve()
        attempts.append(row)
    matrix = []
    for experiment, label in MODES.values():
        rows = [row for row in attempts if row["experiment"] == experiment]
        matrix.append(dict(experiment=experiment, mode=label, availability="present" if rows else "missing",
                           **counts(rows)))
    # Candidate groups match shared experimental knobs; incomplete records never coalesce.
    groups = {}
    for row in attempts:
        key = digest(row["fair_config"])
        if row["missing_comparison_fields"]:
            key += ":incomplete:" + row["run_id"]
        groups.setdefault(key, []).append(row)
    comparisons = []
    for index, rows in enumerate(groups.values(), 1):
        missing = sorted({key for row in rows for key in row["missing_comparison_fields"]})
        # Rule arms have no actor/LLM identity; only match identities among arms
        # which actually share that intervention (E3/E4 both use PPO).
        actors = {row["identity"]["actor_weights_sha256"] for row in rows
                  if row["identity"]["mode"] in ("rule_ppo", "llm_ppo")}
        llm_settings = {(row["identity"]["llm_model"], row["identity"]["llm_max_calls"])
                        for row in rows if row["identity"]["mode"] in ("llm", "llm_ppo")}
        interventions_match = len(actors) <= 1 and len(llm_settings) <= 1
        comparisons.append(dict(group=index, run_ids=[row["run_id"] for row in rows],
                                shared_config_complete=not missing, missing_fields=missing,
                                shared_intervention_identities_match=interventions_match,
                                cross_mode_config_match=not missing and interventions_match and len({row["experiment"] for row in rows}) > 1,
                                formal_strength_evidence=False))
    differences = {}
    for key in attempts[0]["fair_config"] if attempts else ():
        if len({json.dumps(row["fair_config"][key], sort_keys=True) for row in attempts}) > 1:
            differences[key] = {row["run_id"]: row["fair_config"][key] for row in attempts}
    return dict(schema="p6-offline-evaluation-matrix-v1",
                scope="Selected existing attempts only; engineering inventory, not a frozen comparison or strength acceptance",
                denominator_policy="All supplied unique attempts retained; failures/truncations have unknown competitive result, never automatic defeat. Missing modes have zero attempts, not zero win rate.",
                comparison_policy="Shared configuration and source hashes must be complete/equal; mode adapters, actor identity and LLM budget are explicit interventions. Same-policy models/budgets must also match for a formal paired design. No formal design is inferred from artifacts.",
                totals=counts(attempts), matrix=matrix, attempts=attempts,
                duplicate_inputs_ignored=duplicates,
                comparison_groups=comparisons, differing_shared_fields=differences,
                formal_comparison_ready=False,
                limitations=["No sampling frame/planned attempts inferred; caller must include every attempted run in the selected round.",
                             "Descriptive fractions/intervals cannot establish mode advantage; repeated repaired runs are not independent training seeds.",
                             "Game build/opponent version and remote LLM reproducibility may be absent; missing is never assumed equal.",
                             "Local micro truncation is a release event, not match truncation; reward not reconstructed."])


def markdown(report):
    lines = ["# P6 E0–E4 离线评估矩阵 MVP", "", "仅汇总指定历史工件，不运行SC2、API或训练。系统可运行证据与正式强度比较分别判断；本报告不构成正式P6验收或模式胜率优势。", "",
             "| 模式 | 证据 | attempts | 完整已知结果 | failed | 整场truncated | unknown状态 | 胜/负/平 | 未知结果 |", "|---|---|---:|---:|---:|---:|---:|---|---:|"]
    for row in report["matrix"]:
        lines.append(f"| {row['experiment']} {row['mode']} | {row['availability']} | {row['attempts']} | {row['completed']} | {row['failed']} | {row['truncated']} | {row['unknown']} | {row['wins']}/{row['losses']}/{row['ties']} | {row['unknown_results']} |")
    lines += ["", "attempt分母保留全部输入；unknown不记负或胜。JSON中的已知结果胜率/Wilson区间仅描述所选记录，端到端Victory比例使用全部attempt分母；两者不能相互替代。missing模式的比率为null。", "", "| run | 状态 | 结果 | LLM预算/采用步 | PPO推理/owned | 局部micro截断 |", "|---|---|---|---|---|---:|"]
    for row in report["attempts"]:
        m = row["metrics"]
        lines.append(f"| `{row['run_id']}` | {row['status']} | {row['outcome']} | {row['identity']['llm_max_calls']}/{m['llm_steps']} | {m['ppo_inference_decisions']}/{m['micro_owned_decisions']} | {m['local_micro_truncated']} |")
    lines += ["", "公平配置包含地图及SHA、对手、难度、实时/步进、seed、时限、控数、Ares/packages、共享执行器源码与game build。模式、模式适配源码、actor SHA、LLM模型/预算/请求日期单列；不会因为Rule/LLM或Rule/PPO的预期差异直接拒绝跨模式匹配，也不按模型路径斜杠判身份。缺失字段不会默认相等。", "",
              "当前各run缺失项："]
    for row in report["attempts"]:
        lines.append(f"- `{row['run_id']}`: {', '.join(row['missing_comparison_fields']) or '无'}。")
    lines += ["", "观测到的共享配置差异：" + (", ".join(report["differing_shared_fields"]) or "无已记录差异") + "。详见JSON逐run配置与源SHA。即使配置完整相同，也须预冻结评估轮次、交叉顺序、多地图/种子及独立训练种子，不能从当前记录自动推导正式比较资格。", "",
              "失败attempt始终计入端到端分母，必要修复后的成功不消除首次失败。不同源码/预算或配置单局不能拼接成模式强度结论。原始artifact不修改；JSON保留读取文件SHA、project commit和工作树diff身份。LLM预算与实际采用不是同一指标；局部micro截断不代表整场截断。", "",
              "复现（run ID在artifacts/runs下；自定义目录输入时替换为原目录）：", "", "```powershell", "python -s tools/report_evaluation_matrix.py " + " ".join('"' + row["run_id"] + '"' for row in report["attempts"]) + " --output docs/validation/p6_evaluation_matrix_mvp.json --markdown docs/PHASE_06_EVALUATION_MATRIX_MVP_REPORT.md", "```", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", help="run IDs under artifacts/runs, or existing run directories")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    paths = [Path(name) if Path(name).is_dir() else ROOT / "artifacts/runs" / name for name in args.runs]
    if not all(path.is_dir() for path in paths):
        parser.error("all run directories must exist (missing evidence files within a run are retained)")
    try:
        report = build_report(paths)
    except ValueError as exc:
        parser.error(str(exc))
    # Reports must never overwrite selected raw evidence, including through symlinks.
    outputs = [args.output] + ([args.markdown] if args.markdown else [])
    if any(target.resolve().is_relative_to(run.resolve()) for target in outputs for run in paths):
        parser.error("output must stay outside input run directories")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(report), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "attempts": report["totals"]["attempts"]}))


if __name__ == "__main__":
    main()
