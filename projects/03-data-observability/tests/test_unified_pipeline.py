"""Spark pipeline vs. an independent pandas calculation, plus exact checks on the planted problems."""
import json

import pandas as pd
import pytest

from observability.kpi import monthly_kpis
from observability.lake_pipeline import run
from observability.sources import START, make_sources

DAYS = 62                                               # Aug + Sep, small and quick


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    root = tmp_path_factory.mktemp("obs")
    src, out = root / "src", root / "out"
    src.mkdir()
    tables, counts = make_sources(n_datasets=120, days=DAYS, seed=3)
    for n, df in tables.items():
        df.to_csv(src / f"{n}.csv", index=False)
    end = (START + pd.Timedelta(days=DAYS - 1)).strftime("%Y-%m-%d")
    m = run(src, out, START.strftime("%Y-%m-%d"), end)
    fact = pd.concat(pd.read_csv(p) for p in (out / "daily_fact").glob("part-*.csv"))
    return tables, counts, m, fact, out


def test_rejects_exactly_the_planted_rows(result):
    _, c, m, _, _ = result
    assert m["dq_rows_rejected"] == c["dq_duplicates"] + c["dq_orphans"] + c["dq_bad_status"]
    assert m["dq_rows_clean"] == c["dq_rows_good"]


def test_reconciles_and_writes_manifest(result):
    _, _, m, _, out = result
    assert m["status"] == "success" and all(m["reconciliation"].values())
    assert json.loads((out / "_manifest.json").read_text())["status"] == "success"


def test_one_row_per_dataset_per_day(result):
    _, _, m, fact, _ = result
    assert len(fact) == 120 * DAYS and not fact.duplicated(["dataset_id", "day"]).any()
    assert m["fact_rows"] == len(fact)


def test_kpis_match_independent_pandas_oracle(result):
    tables, _, _, fact, _ = result
    reg = tables["registry"].set_index("dataset_id")
    crit = reg[["feeds_high_priority_use", "tagged_data_product", "has_high_priority_elements"]].any(axis=1)
    crit_ids = set(crit[crit].index)
    lin = tables["lineage_edges"]
    lin = lin[(lin.dataset_id != lin.upstream_dataset_id) & lin.dataset_id.isin(reg.index)]
    lin_first = lin.groupby("dataset_id")["captured_date"].min()
    mon_first = tables["monitor_enrollment"].groupby("dataset_id")["enrolled_date"].min()
    dq = tables["dq_results"].drop_duplicates("result_id")
    dq = dq[dq.status.isin(["pass", "fail"]) & dq.dataset_id.isin(reg.index)]
    dq["month"] = dq.run_date.str[:7]

    got = monthly_kpis(fact).set_index("month")
    for month, last_day in (("2026-08", "2026-08-31"), ("2026-09", START.strftime("%Y-%m-%d"))):
        if month == "2026-09":
            last_day = (START + pd.Timedelta(days=DAYS - 1)).strftime("%Y-%m-%d")
        q_ids = set(dq[dq.month == month].dataset_id)
        full = [d for d in crit_ids if d in lin_first.index and lin_first[d] <= last_day
                and d in mon_first.index and mon_first[d] <= last_day and d in q_ids]
        assert got.loc[month, "fully_covered_pct"] == round(100 * len(full) / len(crit_ids), 1)


def test_rerun_gives_same_result(result, tmp_path):
    tables, _, m, _, _ = result
    # idempotence: running again over the same inputs overwrites and reports identical counts
    src = tmp_path / "src"
    src.mkdir()
    for n, df in tables.items():
        df.to_csv(src / f"{n}.csv", index=False)
    end = (START + pd.Timedelta(days=DAYS - 1)).strftime("%Y-%m-%d")
    out = tmp_path / "out"
    a = run(src, out, START.strftime("%Y-%m-%d"), end)
    b = run(src, out, START.strftime("%Y-%m-%d"), end)
    assert {k: a[k] for k in ("dq_rows_clean", "fact_rows")} == {k: b[k] for k in ("dq_rows_clean", "fact_rows")}
