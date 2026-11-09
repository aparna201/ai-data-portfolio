"""Back-of-envelope value model for the collections agent.

    python scripts/estimate_impact.py

EVERY number below is a placeholder assumption, not a measurement. Replace them with the hospital's own
figures (open overdue bills, average value, minutes per manual chase, cost of capital) before quoting anything.
"""
# --- assumptions (edit these) ---
OPEN_OVERDUE_BILLS = 300          # corporate-paid bills overdue at any time
AVG_BILL_INR = 25_000
REMINDERS_PER_BILL_PER_MONTH = 3  # manual chasing today
MINUTES_PER_MANUAL_REMINDER = 8   # find bill, write, send, log
STAFF_COST_INR_PER_HOUR = 250
DAYS_COLLECTED_EARLIER = 5        # assumed average speed-up from consistent follow-up
ANNUAL_COST_OF_CAPITAL = 0.10
SHARE_OF_REMINDERS_AUTOMATED = 0.9   # exceptions and disputes still need a person

hours_saved = (OPEN_OVERDUE_BILLS * REMINDERS_PER_BILL_PER_MONTH * MINUTES_PER_MANUAL_REMINDER / 60
               * SHARE_OF_REMINDERS_AUTOMATED)
staff_saving = hours_saved * STAFF_COST_INR_PER_HOUR
outstanding = OPEN_OVERDUE_BILLS * AVG_BILL_INR
float_saving_per_month = outstanding * ANNUAL_COST_OF_CAPITAL / 365 * DAYS_COLLECTED_EARLIER

print(f"Outstanding in scope:          INR {outstanding:,.0f}")
print(f"Staff hours saved per month:   {hours_saved:,.0f} h")
print(f"Staff cost saved per month:    INR {staff_saving:,.0f}")
print(f"Financing cost saved / month:  INR {float_saving_per_month:,.0f}  (if bills clear {DAYS_COLLECTED_EARLIER} days sooner)")
print(f"Total per month (illustrative): INR {staff_saving + float_saving_per_month:,.0f}")
