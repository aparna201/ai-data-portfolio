"""Stand-ins for the hospital's separate systems. In real life each is an API call (FHIR, REST, a vendor SDK).

The gateway never copies this data. It asks the system on every request, then filters what comes back.
All names and values are invented.
"""
from copy import deepcopy

PATIENTS = [  # patient_id, name, dob, phone, ward, diagnosis, medications, allergies
    (1, "Asha Verma", "1971-03-02", "555-0101", "A", "type 2 diabetes", "metformin", "penicillin"),
    (2, "Ravi Kumar", "1958-11-20", "555-0102", "A", "hypertension", "amlodipine", "none"),
    (3, "Meera Nair", "1989-07-14", "555-0103", "B", "appendicitis", "post-op analgesia", "none"),
    (4, "Sanjay Rao", "1964-01-30", "555-0104", "B", "knee replacement", "enoxaparin", "latex"),
    (5, "Leela Devi", "1952-09-09", "555-0105", "A", "heart failure", "furosemide", "none"),
    (6, "Imran Khan", "1993-05-25", "555-0106", "B", "fracture", "ibuprofen", "none"),
]
FIELDS = ("patient_id", "name", "dob", "phone", "ward", "diagnosis", "medications", "allergies")

LAB = [  # result_id, patient_id, test, value, flag, status
    (1, 1, "HbA1c", 8.1, "high", "final"), (2, 2, "creatinine", 1.0, "normal", "final"),
    (3, 3, "WBC", 14.2, "high", "final"), (4, 4, "INR", 1.1, "normal", "pending"),
    (5, 5, "BNP", 640.0, "high", "final"), (6, 6, "Hb", 13.5, "normal", "final"),
]
LAB_FIELDS = ("result_id", "patient_id", "test", "value", "flag", "status")

CARE_TEAMS = {"d_rao": {1, 2, 5}, "d_iyer": {3, 4}, "d_khan": {6}}   # doctor -> patients they treat
SLOTS = ("08:00", "10:00", "12:00", "14:00")
ROOMS = ("OR-1", "OR-2")


class RecordsSystem:
    def get(self, patient_id: int | None = None) -> list[dict]:
        rows = [dict(zip(FIELDS, p)) for p in PATIENTS]
        return [r for r in rows if patient_id is None or r["patient_id"] == patient_id]

    def ward_of(self, patient_id: int) -> str | None:
        rows = self.get(patient_id)
        return rows[0]["ward"] if rows else None


class LabSystem:
    def get(self, patient_id: int | None = None) -> list[dict]:
        rows = [dict(zip(LAB_FIELDS, r)) for r in LAB]
        return [r for r in rows if patient_id is None or r["patient_id"] == patient_id]


class ORScheduler:
    """Room x date x slot. `booked_by_patient` is private to the scheduler; the gateway never returns it to housekeeping."""

    def __init__(self) -> None:
        self.bookings: dict[tuple, dict] = {("OR-1", "2026-11-10", "08:00"): {"patient_id": 3, "surgeon": "d_iyer"}}
        self.needs_cleaning: set[tuple] = {("OR-2", "2026-11-10", "10:00")}

    def availability(self, date: str) -> list[dict]:
        out = []
        for room in ROOMS:
            for slot in SLOTS:
                key = (room, date, slot)
                state = "booked" if key in self.bookings else ("cleaning" if key in self.needs_cleaning else "free")
                out.append({"room": room, "date": date, "slot": slot, "state": state})
        return out

    def book(self, room: str, date: str, slot: str, patient_id: int, surgeon: str) -> bool:
        key = (room, date, slot)
        if room not in ROOMS or slot not in SLOTS or key in self.bookings or key in self.needs_cleaning:
            return False
        self.bookings[key] = {"patient_id": patient_id, "surgeon": surgeon}
        return True

    def mark_cleaned(self, room: str, date: str, slot: str) -> bool:
        key = (room, date, slot)
        if key not in self.needs_cleaning:
            return False
        self.needs_cleaning.discard(key)
        return True


class Systems:
    def __init__(self) -> None:
        self.records, self.lab, self.scheduler = RecordsSystem(), LabSystem(), ORScheduler()
        self.care_teams = deepcopy(CARE_TEAMS)
