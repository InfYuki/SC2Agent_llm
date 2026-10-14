"""Summarize actual strategy events, including failures and overlap checks."""
import argparse
from collections import Counter
import json
from pathlib import Path
import statistics


def summarize(run):
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    events = [
        json.loads(line)
        for line in (run / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    requests = [e for e in events if e["event"] == "llm_request"]
    responses = [e for e in events if e["event"] == "llm_response"]
    plans = [e for e in events if e["event"] == "llm_plan"]
    latencies = sorted(
        e["latency_seconds"] for e in responses if "latency_seconds" in e
    )
    tokens = Counter()
    for event in responses:
        tokens.update(event.get("usage", {}))
    outstanding, peak, violations = set(), 0, []
    for event in events:
        if event["event"] == "llm_request":
            outstanding.add(event["request_id"])
            peak = max(peak, len(outstanding))
        elif event["event"] == "llm_response":
            outstanding.discard(event["request_id"])
        elif event["event"] == "llm_plan" and event["status"] != "expired":
            age = event["game_seconds"] - event["captured_game_seconds"]
            if not 0 <= age <= 45:
                violations.append(dict(request_id=event["plan"]["request_id"], age=age))
    strategy_file = run / "strategy_summary.json"
    strategy = (
        json.loads(strategy_file.read_text(encoding="utf-8"))
        if strategy_file.is_file()
        else None
    )
    counters = strategy["counters"] if strategy else {}
    steps = counters.get("rule_steps", 0) + counters.get("llm_steps", 0)
    return dict(
        run_id=run.name,
        mode=strategy["mode"] if strategy else "rule",
        summary=summary,
        requests=len(requests),
        responses=len(responses),
        valid_plans=len(plans),
        failures=dict(
            Counter(e["category"] for e in events if e["event"] == "llm_failure")
        ),
        plan_tasks=dict(Counter(e["plan"]["task"] for e in plans)),
        plan_statuses=dict(Counter(e["status"] for e in plans)),
        latency_mean_seconds=statistics.mean(latencies) if latencies else None,
        latency_p95_seconds=latencies[int(0.95 * (len(latencies) - 1))]
        if latencies
        else None,
        latency_max_seconds=max(latencies) if latencies else None,
        input_tokens_min=min(
            (e.get("usage", {}).get("prompt_tokens", 0) for e in responses),
            default=None,
        ),
        input_tokens_max=max(
            (e.get("usage", {}).get("prompt_tokens", 0) for e in responses),
            default=None,
        ),
        total_usage=dict(tokens),
        max_concurrent_requests=peak,
        unmatched_requests_at_exit=len(outstanding),
        freshness_violations=violations,
        llm_step_fraction=counters.get("llm_steps", 0) / steps if steps else None,
        callbacks_while_waiting=counters.get("callbacks_while_waiting", 0),
        strategy_counters=counters,
        median_game_advance_during_request=statistics.median(
            e["game_seconds"] - e["captured_game_seconds"] for e in responses
        )
        if responses
        else None,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", nargs="+", help="run IDs inside artifacts/runs")
    parser.add_argument("--output", default="docs/validation/strategy_v1_metrics.json")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    reports = [summarize(root / "artifacts" / "runs" / name) for name in args.runs]
    target = root / args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            dict(
                scope="Small engineering pilot; no strategic strength claim",
                runs=reports,
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps({"output": str(target), "run_ids": [r["run_id"] for r in reports]})
    )


if __name__ == "__main__":
    main()
