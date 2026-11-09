"""Turn a plain-English question into a QueryPlan.

`RuleBasedTranslator` is a keyword demo so the project runs with no API key.
To use an LLM, write a translator with the same `parse(question)` method that asks the
model for JSON and returns `plan_from_json(json.loads(reply))`. The policy check in
`plan.build_sql` still applies to whatever the model produces.
"""
import re

from .plan import Filter, QueryPlan


STOP_WORDS = {"total", "all", "the", "general", "there"}   # "patients in total" is not a city


class RuleBasedTranslator:
    def parse(self, question: str) -> QueryPlan:
        q = question.lower()

        if re.search(r"invoice|bill|payment|unpaid|owe", q):
            table = "invoices"
        elif re.search(r"appointment|visit|booking|schedule", q):
            table = "appointments"
        elif "patient" in q:
            table = "patients"
        else:
            raise ValueError("I couldn't tell whether you mean patients, appointments or invoices.")

        filters: list[Filter] = []
        if table == "invoices":
            if "unpaid" in q:
                filters.append(Filter("status", "=", "unpaid"))
            elif re.search(r"\bpaid\b", q):
                filters.append(Filter("status", "=", "paid"))
        elif table == "appointments":
            for status in ("cancelled", "completed", "scheduled"):
                if status in q:
                    filters.append(Filter("status", "=", status))
            if m := re.search(r"\bdr\.?\s+([a-z]+)", q):
                filters.append(Filter("doctor", "=", f"Dr. {m.group(1).title()}"))
            if m := re.search(r"\d{4}-\d{2}-\d{2}", q):
                filters.append(Filter("appt_date", "=", m.group(0)))
        elif (m := re.search(r"\b(?:in|from|city is)\s+([a-z]+)", q)) and m.group(1) not in STOP_WORDS:
            filters.append(Filter("city", "=", m.group(1).title()))

        if re.search(r"how many|count|number of", q):
            return QueryPlan(table, filters=filters, aggregate="count")
        if table == "invoices" and re.search(r"\btotal\b|\bsum\b", q):
            return QueryPlan(table, filters=filters, aggregate="sum", sum_column="amount")
        return QueryPlan(table, filters=filters)
