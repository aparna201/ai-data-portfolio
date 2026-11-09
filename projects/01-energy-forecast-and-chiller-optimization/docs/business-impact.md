# Business impact: how the number is built

```
annual saving ($) = (baseline kWh - optimized kWh) / hours simulated * 8760 * tariff ($/kWh)
```

| Input | Value used | Source |
|---|---|---|
| Hours simulated | 407 (held-out test block) | `reports/split_info.json` |
| Baseline kWh | 80,279 | `reports/impact.csv` |
| Forecast-planned kWh | 79,434 (1.05% lower) | same |
| Oracle kWh | 79,248 (1.28% lower) | same |
| Tariff | $0.12/kWh | **assumption**, `reports/impact_assumptions.json` |

Result: about 18,186 kWh and $2,182 per year for this small synthetic plant.

## What this does and does not show

- It shows forecast quality converts into energy savings, and that most of the possible saving (82%) is captured by a realistic forecast.
- It does not show what a real plant saves. Real savings depend on the plant's curves, load profile and tariff structure (demand charges, time-of-use).
- Before quoting a client, measure baseline from their metered data and verify with a before/after or weather-normalised comparison.

## Your real figures

<!-- ADD-REAL: result from the original project. Write: metric, baseline, how it was measured, time period. Do not include anything you cannot explain in an interview. -->
