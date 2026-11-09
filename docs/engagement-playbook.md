# How I run an engagement (forward-deployed style)

The same sequence behind every project here.

## Week 1: understand the problem, not the tool
- **Who loses time or money today, and how much?** Get a number: hours a week, rupees or dollars a month, an SLA breached.
- **Walk the process with the people doing it.** Sit with billing, operators or analysts. Write down every spreadsheet, export and inbox.
- **Inventory sources.** Databases, APIs, files, who owns each, how fresh, how clean.
- **Ask the privacy questions early.** What is personal or regulated data? Who approves where it can go? Can it reach an external model?
- **Agree what "better" means.** One metric, a baseline, and who will check it.

## Weeks 2 to 3: smallest design that works
- Draw current and proposed architecture on one page each.
- Build a **baseline first** (a rule, last week's value, a spreadsheet formula). Anything fancier must beat it.
- Use **synthetic or sampled data** to prove the pipeline before touching real records.
- Split data **in time or by group**. Tune on one slice, choose on another, score the last slice once.

## Weeks 4 to 6: pilot with guard rails
- **Dry run by default.** Drafts and reports first; nothing sent or changed until someone approves.
- **Reconcile.** Totals out must equal totals in. Make the system prove it.
- **Humans in the loop** for disputes, money movement and anything irreversible.
- **Log everything**: what was asked, decided and sent.

## Showing the business case
| Ask | How I answer |
|---|---|
| What does it save? | Hours saved x loaded hourly cost, or cash collected earlier x cost of capital, with every input listed |
| How do you know? | Before/after on the same measure, same period, same people |
| What could go wrong? | A short risk list with owner and mitigation |
| What did you not measure? | Said plainly, with the plan to measure it |

## Checklist before go-live
- [ ] Baseline and test score recorded, including where the model is weak
- [ ] Privacy and compliance sign-off for real data
- [ ] Read-only access wherever writes are not needed
- [ ] Alerts go to a person who can act, with a clear next step
- [ ] A rollback: switch it off and the old process still works
- [ ] A named owner for monitoring after launch
