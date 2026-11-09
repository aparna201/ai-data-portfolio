// Runs agent1_aging_analyser.js outside n8n so it can be checked against the Python version.
//   node run_agent1.js ../data/bills.csv 2026-11-08   -> JSON array of decisions on stdout
const fs = require('fs');
const path = require('path');
const { DateTime, Settings } = require('luxon');

const [csvPath, asOf] = process.argv.slice(2);
Settings.defaultZone = 'Asia/Kolkata';
const FIXED_NOW = DateTime.fromISO(`${asOf}T10:00:00`, { zone: 'Asia/Kolkata' }).toMillis();  // computed once, before overriding the clock
Settings.now = () => FIXED_NOW;

function parseCsv(text) {            // small CSV reader that understands "quoted, values"
  const rows = []; let row = [], cur = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"' && text[i + 1] === '"') { cur += '"'; i++; } else if (c === '"') q = false; else cur += c; }
    else if (c === '"') q = true;
    else if (c === ',') { row.push(cur); cur = ''; }
    else if (c === '\n') { row.push(cur); rows.push(row); row = []; cur = ''; }
    else if (c !== '\r') cur += c;
  }
  if (cur || row.length) { row.push(cur); rows.push(row); }
  const [head, ...body] = rows.filter(r => r.length > 1);
  return body.map(r => Object.fromEntries(head.map((h, i) => [h, r[i]])));
}

const code = fs.readFileSync(path.join(__dirname, 'agent1_aging_analyser.js'), 'utf8');
const node = new Function('$input', 'DateTime', code);
const out = parseCsv(fs.readFileSync(csvPath, 'utf8')).map(r => {
  const o = node({ item: { json: r } }, DateTime).json.output;
  return { invoice_no: r.invoice_no, ...o };
});
console.log(JSON.stringify(out));
