# AI & Data Engineering Portfolio

**Aparna Hanumantu** · data science and AI engineer, 10+ years across banking, healthcare, hospitality and research, in the US and India.

I build systems that start from a business problem and end with a number someone cares about. This repo holds five of them, rebuilt on **synthetic data** so I can show the work without exposing any employer's or client's data.

Each project folder reads the same way, the way I would explain it to a client:

> 1. the business problem → 2. how it works today → 3. the architecture I would propose → 4. sample data and code → 5. the methods I compared → 6. how I trained, tuned and chose → 7. results on data the model had not seen → 8. the business impact, honestly stated

New here? Read [`docs/WALKTHROUGH.md`](docs/WALKTHROUGH.md): one plain step-by-step document covering all five projects.

## The five projects at a glance

| # | Business problem | What I built | Headline result (synthetic data) | Stack |
**Start with project 04**, the hospital receivables agent. It shows the full path from a business problem to a tested, importable workflow.
|---|---|---|---|---|
| [04](projects/04-hospital-receivables-agent) | Hospital bills sit unpaid because chasing is manual | Two n8n workflows with four agents, plus a tested Python twin of the rules | Rule engine matches its JavaScript version on every test date; 44 tests | n8n, Gemini, Python |
| [01](projects/01-energy-forecast-and-chiller-optimization) | A campus overpays to cool its buildings | Day-ahead load forecast, then a chiller dispatch optimizer | Forecast error 33% below the best naive baseline; about 1% energy saving on a made-up plant (illustrative dollars) | Python, scikit-learn, SciPy; MATLAB versions (not run) |
| [02](projects/02-publishing-analytics-spark) | Product teams spent 40+ hours a month hand-building volume metrics | PySpark pipeline to a daily table, reconciliation, month-over-month KPIs | Daily table reconciles to the cleaned data exactly; the report's 40 hours/month saving is from the project record | PySpark, pandas |
| [03](projects/03-data-observability) | Three observability tools, three databases, and a monthly coverage report stitched by hand | PySpark unifies lineage, quality and monitoring into one daily table; pandas KPI for coverage of critical datasets; extra anomaly-alerting benchmark (Part B, my addition) | Rejected rows equal the planted problems exactly; Spark KPI matches an independent pandas check; the reporting saving (about 40 hours to about 1 a month) is from the project record | PySpark, pandas, scikit-learn | 
| [05](projects/05-clinical-access-gateway) | Many hospital systems, per-app logins, no single governed door for staff or AI assistants | One gateway: role plus relationship checks, break-glass, tamper-evident audit, MCP tools; no-show model as the AI tier; plain-English query layer as Part B | 37 tests incl. access rules and audit tampering; no-show test AUC 0.73 (top 20% holds 39% of no-shows) on synthetic data where logistic wins by construction | Python, MCP, scikit-learn |

## What is real and what is not

- **Synthetic data everywhere.** The patterns come from real work; the plants, bills, patients and volumes are invented. Dollar and rupee figures in the READMEs are worked examples with stated assumptions, not claims about any employer or client.
- **Not run, and labelled so:** the MATLAB files in project 01 (no MATLAB was available), any Gemini or other LLM call (no key was used, so no LLM accuracy is reported), and the n8n workflows in project 04, which n8n's importer accepts but I have not executed.
- **Honest limits.** Several results are modest on purpose. The READMEs say where a method barely beat a baseline, where a test score dropped from the tuned set, and what I did not measure.
- **Credits.** Project 04 adapts a community "collections follow-up agent" template for agencies; the hospital design, rules, fixes and tests are mine.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -r projects/02-publishing-analytics-spark/requirements.txt    # needs Java 17 or 21
npm install --prefix projects/04-hospital-receivables-agent/n8n          # optional: JS parity test
pytest -q                                                                # about 115 tests
```

Each project has numbered scripts, run in order, for example project 01:

```bash
python projects/01-energy-forecast-and-chiller-optimization/scripts/01_generate_data.py
python projects/01-energy-forecast-and-chiller-optimization/scripts/02_train_and_tune.py
```

## Layout

```
docs/                     WALKTHROUGH.md (start here), engagement-playbook.md
projects/
  01-energy-forecast-and-chiller-optimization/   chiller_opt/  scripts/  matlab/  reports/  docs/  tests/
  02-publishing-analytics-spark/                 publishing_etl/  scripts/  reports/  docs/  tests/
  03-data-observability/                         observability/  scripts/  reports/  tests/
  04-hospital-receivables-agent/                 receivables_agent/  n8n/  scripts/  docs/  tests/
  05-clinical-access-gateway/              gateway/  clinic_query/  scripts/  tests/
```

## License

MIT
