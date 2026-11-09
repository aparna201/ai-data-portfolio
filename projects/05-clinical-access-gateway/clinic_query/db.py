"""Synthetic clinic database. All names, phones and amounts are invented."""
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE patients (patient_id INTEGER PRIMARY KEY, name TEXT, phone TEXT, city TEXT);
CREATE TABLE appointments (appt_id INTEGER PRIMARY KEY, patient_id INTEGER, doctor TEXT,
                           appt_date TEXT, status TEXT);
CREATE TABLE invoices (invoice_id INTEGER PRIMARY KEY, patient_id INTEGER, amount REAL, status TEXT);
"""

PATIENTS = [
    (1, "Asha Verma", "555-0101", "Vizag"), (2, "Ravi Kumar", "555-0102", "Hyderabad"),
    (3, "Meera Nair", "555-0103", "Vizag"), (4, "Sanjay Rao", "555-0104", "Chennai"),
    (5, "Leela Devi", "555-0105", "Vizag"), (6, "Imran Khan", "555-0106", "Hyderabad"),
]
APPOINTMENTS = [
    (1, 1, "Dr. Rao", "2026-11-09", "scheduled"), (2, 2, "Dr. Rao", "2026-11-09", "scheduled"),
    (3, 3, "Dr. Rao", "2026-11-10", "cancelled"), (4, 4, "Dr. Iyer", "2026-11-09", "completed"),
    (5, 5, "Dr. Iyer", "2026-11-10", "scheduled"), (6, 6, "Dr. Khan", "2026-11-11", "scheduled"),
]
INVOICES = [
    (1, 1, 1200.0, "paid"), (2, 2, 800.0, "unpaid"), (3, 3, 450.0, "unpaid"),
    (4, 4, 300.0, "paid"), (5, 5, 2200.0, "unpaid"), (6, 6, 150.0, "paid"),
]


def create_demo_db(path: str | Path) -> None:
    path = Path(path)
    path.unlink(missing_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO patients VALUES (?,?,?,?)", PATIENTS)
        conn.executemany("INSERT INTO appointments VALUES (?,?,?,?,?)", APPOINTMENTS)
        conn.executemany("INSERT INTO invoices VALUES (?,?,?,?)", INVOICES)


def connect_read_only(path: str | Path) -> sqlite3.Connection:
    """Open the database so that writes are impossible, whatever SQL is run."""
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)
