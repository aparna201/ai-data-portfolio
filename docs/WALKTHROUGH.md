# Walkthrough: how to explain each project, step by step

One document, plain language. Use it to walk through the repo in an interview, or to read it yourself in order.

## The same eight steps every time

1. **Business problem.** Who loses money or time, and how?
2. **Today.** What data and tools exist now, and what hurts?
3. **Proposed design.** The smallest architecture that fixes the pain.
4. **Sample data.** Synthetic, with the problems built in on purpose so results can be checked.
5. **Methods.** What I tried; the plain baseline comes first.
6. **Training and choosing.** Split the data in time or by group; tune on one part, choose on another.
7. **Test result.** Score once on data nobody tuned on. Report the gap if there is one.
8. **Business impact.** Hours, money, risk, with assumptions stated.

Two habits worth saying out loud: *a baseline comes before a fancy model*, and *the test set is looked at once*.

---

## 01 Energy forecast and chiller optimization

**Story in one breath:** a campus cooling plant has three chillers with different sweet spots. If we know tomorrow's demand, we can choose which chillers to run and how hard. Like a delivery fleet: know tomorrow's parcels, pick the vans.

1. **Problem.** Operators stage chillers by rule of thumb, so the plant burns extra electricity.
2. **Today.** Data sits in a plant historian; analysis is manual exports and scripts (MATLAB in the original work).
3. **Design.** Historian and weather in, hourly features, a day-ahead forecast, an optimizer, a recommendation for the operator, then measure and verify.
4. **Data.** 120 days of hourly load with a daily cycle, weekend dip, temperature effect and noise.
5. **Methods.** Two naive baselines (same hour yesterday, same hour last week), ridge, random forest, gradient boosting. For dispatch, two solvers: SLSQP and differential evolution.
6. **Choosing.** Chronological 70/15/15 split. Tune with time-aware cross-validation on train, compare on validation, refit the winner on train plus validation.
7. **Test.** Gradient boosting error 62 kW against 92 kW for the best naive baseline, about 33% lower. The three ML models are all close because the noise cannot be predicted.
8. **Impact.** About 1% energy saving on this plant, roughly $2,182 a year at an assumed $0.12 per kWh. State that the dollars are illustrative.

**Run:** `scripts/01` to `04` in the project folder.
**Likely question:** *Why not an LSTM?* The MATLAB file shows how; with 120 days of data a tree model is easier to defend, and I would test an LSTM only with more history.

## 02 Publishing analytics (PySpark)

**Story:** every month someone hand-counted how many files and records each engine published. Now a nightly job totals each day, and the month is a sum of 30 totals. Like a shop's till tally versus counting every receipt.

1. **Problem.** Over 40 hours a month of manual querying, each query 30 to 60 minutes, errors in spreadsheets.
2. **Today.** Separate logs per platform, queries by hand, numbers pasted into sheets.
3. **Design.** PySpark job: validate, remove duplicates, aggregate by day; a quality gate; a reconciliation check; a manifest; then month-over-month KPIs for a dashboard.
4. **Data.** 465 raw rows over 92 days with 13 duplicates and 8 invalid rows injected on purpose.
5. **Choices.** Typed once, dedupe by file id, per-day averages so months of different length compare fairly, Parquet partitioned by day, safe reruns.
6. **Tuning.** Spark's default 200 shuffle partitions was about 3 times slower than 4 on small data. Measure, do not trust defaults.
7. **Test.** The job reports exactly the injected problems; daily totals equal cleaned totals. 12 tests.
8. **Impact.** 40 hours a month saved, from the project record. Money figure needs an hourly rate, so it is an assumption.

**Likely questions:** *Streaming?* No, this is batch; streaming would need a watermark for deduplication. *Why only 1.5 times faster from the daily table?* The data is small; Spark's fixed overhead dominates. The benefit is at billions of rows. *The bug I caught:* the first MoM divided by days the engine appeared on, which made a shrinking engine look like it grew.

## 03 Data observability

**Story:** three security companies guard one building, each with its own logbook. The fix is one shared logbook that updates itself, and one number: which critical doors are covered by all three?

1. **Problem.** Lineage, data quality and monitoring tools each kept their own database; the monthly coverage report was stitched by hand.
2. **Today.** Manual exports and spreadsheet lookups, about 40 hours a month (project record; confirm it is not the same 40 hours as project 02).
3. **Design.** PySpark cleans each source, builds one dataset-by-day table, reconciles it; pandas rolls it up monthly. "Critical" is defined once in code.
4. **Data.** Four synthetic tables, 400 datasets, 92 days, with duplicates, orphans, bad statuses and self-loops planted.
5. **Methods.** Exact cleaning rules and joins, not a model. Spark for the expansion, pandas for the small monthly roll-up.
6. **Checking.** Rejected rows equal the planted ones; fact totals equal clean totals; an independent pandas calculation gives the same KPI; reruns match. 19 tests including Part B.
7. **Result.** Fully covered critical datasets rise from 1.9% to 30.2% over three months on synthetic data; timeliness checks fail most. Shows the pipeline works, not a real outcome.
8. **Impact.** About 40 hours to about 1 hour a month, from the project record; plus a gap list to close coverage first.

**Part B (say it is my extra):** an anomaly-alerting benchmark. Four detectors, tuned by metric split, all within F1 0.96 to 1.00 on easy data. I would ship the robust z-score.

**Likely questions:** *Why Spark for this?* The 400 x 92 expansion and joins; the monthly roll-up stays in pandas because it is tiny. *How do you know the numbers are right?* Reconciliation plus an independent oracle. *What would you change at scale?* Partition by date and write incrementally.

## 04 Hospital receivables agent (n8n)

**Story:** a very organised assistant who checks the ledger each morning, sends the right-toned nudge, stops when someone replies, and calls the manager only when a human is needed.

1. **Problem.** Corporate-paid hospital bills sit unpaid; chasing is manual and inconsistent.
2. **Today.** A Google Sheet the billing team updates, hand-written emails, replies missed.
3. **Design.** V1 sends reminders daily; V2 reads replies; the sheet is the shared memory. Four agents: aging (code), reminder writer, escalation writer, reply classifier (Gemini).
4. **Data.** 11 dummy bills, each built to test one rule.
5. **Choices.** Dates by code, not an LLM; "already paid" becomes `paid_claimed` not `paid`; privacy by prompt (no diagnosis or department to the model).
6. **Tuning.** 12 fixes to the template's flaws, listed in `docs/build-notes.md`.
7. **Test.** 44 tests, including that the n8n JavaScript and the Python rules agree on three dates. A keyword reply classifier scores 92% on replies I wrote myself, which is optimistic; no Gemini score exists.
8. **Impact.** A worked example, about 108 staff hours a month on placeholder assumptions. Real pilot numbers go in the marked placeholder.

**Be clear about origin:** the base design is a community template; the hospital changes are the work.

## 05 Clinical access gateway

**Story:** a hotel front desk with a master-key system. Everyone asks the same desk; it checks who you are and which doors your key opens, hands over only what you may have, and writes every request in a ledger that cannot be quietly edited.

1. **Problem.** Hospitals run many systems; staff hop between screens, and AI assistants are blocked on "who may see what, and can you prove it?"
2. **Today.** Per-application roles, ad hoc exports, no single record of who looked at what.
3. **Design.** One gateway holding no data: identify, check role, check the row (care team, ward or own), fetch from the source, keep permitted fields, audit. MCP tools on the front. Break-glass for emergencies with a reason and a review queue.
4. **Data.** Three mock systems (records, lab, OR scheduler), six patients, ten users in six roles, 6,000 synthetic appointments for the AI tier.
5. **Methods.** Tier 1 is rules, no AI. Tier 2 compares logistic regression and gradient boosting for no-show risk.
6. **Choosing.** Appointments split by date: train, validation, test. Pick by validation AUC, refit, score test once.
7. **Test.** 37 tests: row and field rules, deny by default, break-glass, no double booking, audit tampering detected. No-show test AUC 0.73; the riskiest 20% hold 39% of no-shows. Logistic won because my generator is logistic, so say so.
8. **Impact.** Faster access, a defensible audit trail, and AI readiness. The rupee figure for no-shows is illustrative arithmetic with my assumptions.

**Part B:** the earlier plain-English query layer (80% on held-out questions, 13 of 13 attack checks stopped) plugs in as a front end.

**Likely questions:** *Why not let the model decide access?* A prompt can be argued with; a policy table cannot. *Why does a denied patient look the same as a missing one?* So callers cannot probe which ids exist. *What is missing for production?* Single sign-on, real FHIR or vendor adapters, a consent registry, session-bound tokens in MCP, a compliance review.

---

## If you are asked "is this your real work?"

Say: the **patterns and methods** are from my real work; the **data is synthetic** so nothing belongs to an employer or client; the dollar figures are worked examples; and the README for each project says what I did not run or measure.
