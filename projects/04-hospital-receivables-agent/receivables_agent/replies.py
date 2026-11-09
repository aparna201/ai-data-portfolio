"""Agent 4 (reply classifier): what to do when a payer replies.

The n8n workflow asks Gemini to pick an intent. This file holds the parts that are plain rules
(pause lengths, who must be alerted) plus a keyword classifier used as an offline baseline, so
the evaluation harness runs without any API key. Swap in an LLM by passing any function with the
same signature `text -> intent` to `evaluate`.
"""
from __future__ import annotations

from datetime import date, timedelta

# pause_days and urgency come straight from the Agent 4 prompt in n8n/prompts/agent4_reply_classifier.md
PAUSE_DAYS = {"paying_soon": 15, "silent_ack": 5, "disputing": 7, "angry": 7, "already_paid": 30,
              "unclear": 3, "insurance_pending": 30, "needs_payment_plan": 7, "wrong_contact": 90}
URGENCY = {"angry": "high", "disputing": "high", "wrong_contact": "high",
           "needs_payment_plan": "medium", "already_paid": "medium", "insurance_pending": "medium",
           "paying_soon": "low", "silent_ack": "low", "unclear": "low"}
NEEDS_HUMAN = {"angry", "disputing", "already_paid", "needs_payment_plan",
               "insurance_pending", "wrong_contact"}
INTENTS = list(PAUSE_DAYS)

# Order matters: the first rule that matches wins, most specific and most sensitive first.
KEYWORDS = [
    ("wrong_contact", ["passed away", "no longer with us", "wrong person", "not the patient", "wrong address",
                       "wrong contact", "does not work here", "has left the company"]),
    ("angry", ["unacceptable", "stop sending", "stop emailing", "legal", "harass", "fed up", "outrageous",
               "refuse to pay", "will not pay", "complain"]),
    ("already_paid", ["already paid", "have paid", "payment was made", "paid on", "paid it", "transferred on",
                      "utr", "payment done"]),
    ("disputing", ["incorrect", "wrong amount", "never had", "dispute", "not agree", "overcharged",
                   "do not recognise", "does not match", "error in the bill"]),
    ("insurance_pending", ["insurer", "insurance", "tpa", "claim is", "claim has"]),
    ("needs_payment_plan", ["instalment", "installment", "in parts", "more time", "cannot pay in full",
                            "unable to pay the full", "waiver", "payment plan"]),
    ("paying_soon", ["will pay on", "will clear", "will make the payment on", "payment will be made on",
                     "will release", "by the end of", "will transfer on"]),
    ("silent_ack", ["noted", "received your", "acknowledge", "thanks for the reminder", "will look into"]),
]


def classify_keywords(text: str) -> str:
    t = text.lower()
    for intent, words in KEYWORDS:
        if any(w in t for w in words):
            return intent
    return "unclear"


def apply_reply(row: dict, intent: str, today: date) -> dict:
    """The sheet update V2 performs: pause reminders, and flip status when payment is claimed."""
    row = dict(row)
    row["paused_until"] = (today + timedelta(days=PAUSE_DAYS[intent])).isoformat()
    row["status"] = "paid_claimed" if intent == "already_paid" else "overdue"
    return row


def evaluate(samples: list[tuple[str, str]], classify=classify_keywords) -> dict:
    """samples: (reply_text, true_intent). Returns accuracy, per-intent recall and a confusion list."""
    pred = [(classify(text), truth) for text, truth in samples]
    correct = sum(p == t for p, t in pred)
    per_intent = {}
    for intent in INTENTS:
        total = sum(t == intent for _, t in pred)
        if total:
            per_intent[intent] = round(sum(p == t == intent for p, t in pred) / total, 3)
    # Safety view: of replies that truly need a human, how many did we route to one?
    human = [(p, t) for p, t in pred if t in NEEDS_HUMAN]
    human_recall = sum(p in NEEDS_HUMAN for p, _ in human) / len(human)
    return {"n": len(pred), "accuracy": round(correct / len(pred), 3),
            "needs_human_recall": round(human_recall, 3), "per_intent_recall": per_intent,
            "errors": [(txt, t, classify(txt)) for txt, t in samples if classify(txt) != t]}
