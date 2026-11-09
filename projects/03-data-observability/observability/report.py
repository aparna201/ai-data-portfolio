"""Turn anomalies into a short markdown report with an optional LLM summary."""
from typing import Protocol

from .detect import Anomaly


class LLM(Protocol):
    def complete(self, prompt: str) -> str: ...


class OfflineLLM:
    """Echoes the FACTS section of the prompt. Replace with a real model if you like."""

    def complete(self, prompt: str) -> str:
        return prompt.split("FACTS:\n", 1)[-1].strip()


def build_report(anomalies: list[Anomaly], llm: LLM | None = None) -> str:
    llm = llm or OfflineLLM()
    lines = ["# Data Observability Report", "", f"Anomalies found: **{len(anomalies)}**", ""]
    if not anomalies:
        return "\n".join(lines + ["All monitored metrics are within normal range."])

    lines += ["| Metric | Day | Value | Expected | Robust z |", "|---|---|---|---|---|"]
    for a in sorted(anomalies, key=lambda a: -abs(a.z)):
        lines.append(f"| {a.metric} | {a.index} | {a.value:,.4g} | {a.expected:,.4g} | {a.z:+.1f} |")

    facts = "\n".join(
        f"- {a.metric} on day {a.index}: {a.value:,.4g} vs expected {a.expected:,.4g}"
        for a in anomalies
    )
    prompt = f"Summarise these metric anomalies for a data owner in two sentences.\nFACTS:\n{facts}"
    return "\n".join(lines + ["", "## Summary", "", llm.complete(prompt)])
