// n8n Code node: "Agent 1 Aging Analyser"
// Mode: Run Once for Each Item. Language: JavaScript. Paste everything below as the node body.
// n8n supplies `$input` and luxon's `DateTime`. No AI call: dates and cooldowns are exact rules.
const r = $input.item.json;
const TZ = 'Asia/Kolkata';
const today = DateTime.now().setZone(TZ).startOf('day');
const day = v => v ? DateTime.fromISO(String(v).slice(0, 10), { zone: TZ }) : null;
const stamp = v => v ? DateTime.fromISO(String(v)).setZone(TZ).startOf('day') : null;
const since = d => (d && d.isValid) ? Math.floor(today.diff(d, 'days').days) : null;

const due = day(r.due_date);
if (!due || !due.isValid) {
  return { json: { ...r, output: { days_overdue: null, aging_bucket: 'invalid_date', tone_grade: 'none', should_remind: false, escalate_now: false, cooldown_reason: 'missing or invalid due_date' } } };
}
const daysOverdue = Math.floor(today.diff(due, 'days').days);

let bucket, tone, gap;
if (daysOverdue < 0)        { bucket = 'not_due'; tone = 'none';         gap = null; }
else if (daysOverdue <= 15) { bucket = '0-15';    tone = 'gentle';       gap = 7; }
else if (daysOverdue <= 30) { bucket = '16-30';   tone = 'firm';         gap = 5; }
else if (daysOverdue <= 60) { bucket = '31-60';   tone = 'urgent';       gap = 3; }
else if (daysOverdue <= 90) { bucket = '61-90';   tone = 'final_notice'; gap = 7; }
else                        { bucket = '90+';     tone = 'escalate';     gap = null; }

const status = String(r.status || '').toLowerCase();
const closed = ['paid', 'paid_claimed', 'closed', 'waived'].includes(status);
const pausedUntil = day(r.paused_until);
const paused = !!(pausedUntil && pausedUntil.isValid && today < pausedUntil);
const sinceReminder = since(stamp(r.last_reminded_at));
const sinceEscalation = since(stamp(r.last_escalated_at));

let should = false, reason = '';
if (closed) reason = 'status is ' + status;
else if (paused) reason = 'paused until ' + r.paused_until + ' (patient replied)';
else if (daysOverdue < 0) reason = 'not yet due';
else if (tone === 'escalate') reason = 'over 90 days: staff handle directly';
else if (sinceReminder === null || sinceReminder >= gap) should = true;
else reason = 'cooldown active';

const escalate_now = !closed && !paused && daysOverdue >= 60 && (sinceEscalation === null || sinceEscalation >= 7);

return { json: { ...r, output: { days_overdue: daysOverdue, aging_bucket: bucket, tone_grade: tone, should_remind: should, escalate_now, cooldown_reason: reason } } };
