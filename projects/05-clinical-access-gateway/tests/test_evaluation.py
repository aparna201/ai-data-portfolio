from pathlib import Path

import pytest

from clinic_query.db import create_demo_db
from clinic_query.evaluate import ATTACKS, load, run_attacks, score_translator
from clinic_query.translate import RuleBasedTranslator

DATA = Path(__file__).parent.parent / "data"


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "clinic.db"
    create_demo_db(path)
    return path


def test_every_attack_is_stopped_and_the_database_is_untouched(db):
    results = run_attacks(db)
    assert len(results) == len(ATTACKS) + 1
    assert all(r["passed"] for r in results), [r for r in results if not r["passed"]]


def test_dev_set_is_fully_handled_after_tuning(db, tmp_path):
    r = score_translator(load(DATA / "questions_dev.json"), RuleBasedTranslator(), db, tmp_path / "a.jsonl")
    assert r["answer_accuracy"] == 1.0


def test_held_out_test_set_accuracy_is_recorded_honestly(db, tmp_path):
    r = score_translator(load(DATA / "questions_test.json"), RuleBasedTranslator(), db, tmp_path / "a.jsonl")
    assert r["answer_accuracy"] == 0.8                      # 16 of 20; the four misses are paraphrases
    assert "who hasn't paid" in r["misses"]


def test_refusal_questions_count_only_when_refused(db, tmp_path):
    items = [{"role": "doctor", "question": "show me the weather", "refuse": True}]
    assert score_translator(items, RuleBasedTranslator(), db, tmp_path / "a.jsonl")["answer_accuracy"] == 1.0


def test_city_rule_ignores_in_total(db):
    plan = RuleBasedTranslator().parse("how many patients in total")
    assert plan.filters == []
