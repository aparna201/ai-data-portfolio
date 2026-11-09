"""Synthetic source tables for three observability products that each keep their own data.

  lineage_edges       the lineage product: which dataset feeds which
  dq_results          the data-quality product: one row per check run (consistency, validity, timeliness)
  monitor_enrollment  the monitoring-and-alerts product: which datasets are monitored, and since when
  registry            the dataset catalogue, with the flags that make a dataset "critical"

A dataset is CRITICAL when any of: it feeds a high-priority use, it is tagged to a data product, or it
holds high-priority data elements. The story in the data: coverage by all three products grows over three
months. A few real-world problems are injected so validation has work to do.
"""
import numpy as np
import pandas as pd

START = pd.Timestamp("2026-08-01")
CHECKS = {"consistency": 0.97, "validity": 0.95, "timeliness": 0.90}          # pass probabilities
DOMAINS = ["card", "risk", "retail", "commercial"]
COVERAGE_END = {"critical": {"lineage": 0.85, "quality": 0.75, "monitoring": 0.55},
                "other": {"lineage": 0.50, "quality": 0.40, "monitoring": 0.30}}


def make_sources(n_datasets: int = 400, days: int = 92, seed: int = 5) -> tuple[dict, dict]:
    rng = np.random.default_rng(seed)
    ids = [f"DS{i:04d}" for i in range(n_datasets)]
    registry = pd.DataFrame({
        "dataset_id": ids, "domain": rng.choice(DOMAINS, n_datasets),
        "feeds_high_priority_use": rng.random(n_datasets) < 0.15,
        "tagged_data_product": rng.random(n_datasets) < 0.20,
        "has_high_priority_elements": rng.random(n_datasets) < 0.10})
    critical = registry[["feeds_high_priority_use", "tagged_data_product", "has_high_priority_elements"]].any(axis=1)

    start_day = {}                                         # product -> {dataset_id: first covered day index}
    for product in ("lineage", "quality", "monitoring"):
        p = np.where(critical, COVERAGE_END["critical"][product], COVERAGE_END["other"][product])
        covered = rng.random(n_datasets) < p
        first = rng.integers(-30, days, n_datasets)        # negative = already covered when the period starts
        start_day[product] = {i: int(s) for i, s, c in zip(ids, first, covered) if c}

    def date(day_index):
        return (START + pd.Timedelta(days=int(day_index))).strftime("%Y-%m-%d")

    lineage = pd.DataFrame([{"dataset_id": d, "upstream_dataset_id": rng.choice(ids), "captured_date": date(s)}
                            for d, s in start_day["lineage"].items() for _ in range(rng.integers(1, 4))])
    lineage = lineage[lineage["dataset_id"] != lineage["upstream_dataset_id"]]
    monitor = pd.DataFrame([{"dataset_id": d, "enrolled_date": date(s)} for d, s in start_day["monitoring"].items()])

    rows, rid = [], 0
    for d, s in start_day["quality"].items():
        for day in range(max(s, 0), days):
            for check, p in CHECKS.items():
                rows.append((f"R{rid:07d}", d, check, date(day), "pass" if rng.random() < p else "fail"))
                rid += 1
    dq = pd.DataFrame(rows, columns=["result_id", "dataset_id", "check_type", "run_date", "status"])

    counts = {"dq_rows_good": len(dq), "lineage_rows_good": len(lineage), "monitor_rows_good": len(monitor)}

    dupes = dq.sample(round(0.02 * len(dq)), random_state=seed)
    orphans = dq.sample(round(0.01 * len(dq)), random_state=seed + 1).assign(
        dataset_id="DS9999", result_id=lambda x: "O" + x["result_id"])
    bad_status = dq.sample(round(0.005 * len(dq)), random_state=seed + 2).assign(
        status="unknown", result_id=lambda x: "B" + x["result_id"])
    dq_raw = pd.concat([dq, dupes, orphans, bad_status], ignore_index=True).sample(frac=1, random_state=seed)
    self_loops = pd.DataFrame({"dataset_id": ids[:2], "upstream_dataset_id": ids[:2], "captured_date": date(0)})
    lineage_raw = pd.concat([lineage, self_loops], ignore_index=True)
    monitor_raw = pd.concat([monitor, monitor.head(3)], ignore_index=True)

    counts.update({"dq_duplicates": len(dupes), "dq_orphans": len(orphans), "dq_bad_status": len(bad_status),
                   "lineage_invalid": 2, "monitor_duplicates": 3, "days": days,
                   "critical_datasets": int(critical.sum())})
    return {"registry": registry, "lineage_edges": lineage_raw, "dq_results": dq_raw,
            "monitor_enrollment": monitor_raw}, counts
