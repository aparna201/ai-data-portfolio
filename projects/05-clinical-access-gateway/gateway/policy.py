"""The whole access policy in one table. Anything not listed is denied.

(role, resource) -> {actions, fields, scope}
scope says WHICH rows of that resource the person may see:
  all        every row
  care_team  patients on this doctor's own list
  ward       patients in this nurse's ward
  own        the patient's own rows
"""
POLICY: dict[tuple[str, str], dict] = {
    ("doctor", "patient_record"): {"actions": {"read"}, "scope": "care_team",
                                   "fields": ["patient_id", "name", "dob", "ward", "diagnosis", "medications", "allergies"]},
    ("doctor", "lab_results"): {"actions": {"read"}, "scope": "care_team",
                                "fields": ["result_id", "patient_id", "test", "value", "flag", "status"]},
    ("doctor", "or_availability"): {"actions": {"read"}, "scope": "all", "fields": ["room", "date", "slot", "state"]},
    ("doctor", "or_booking"): {"actions": {"book"}, "scope": "care_team", "fields": []},
    ("nurse", "patient_record"): {"actions": {"read"}, "scope": "ward",
                                  "fields": ["patient_id", "name", "ward", "medications", "allergies"]},
    ("nurse", "lab_results"): {"actions": {"read"}, "scope": "ward",
                               "fields": ["result_id", "patient_id", "test", "flag", "status"]},
    ("nurse", "or_availability"): {"actions": {"read"}, "scope": "all", "fields": ["room", "date", "slot", "state"]},
    ("lab_tech", "lab_results"): {"actions": {"read"}, "scope": "all",
                                  "fields": ["result_id", "patient_id", "test", "status"]},
    ("front_desk", "patient_record"): {"actions": {"read"}, "scope": "all", "fields": ["patient_id", "name", "phone"]},
    ("front_desk", "no_show_risk"): {"actions": {"read"}, "scope": "all", "fields": ["patient_id", "risk"]},
    ("housekeeping", "or_availability"): {"actions": {"read"}, "scope": "all", "fields": ["room", "date", "slot", "state"]},
    ("housekeeping", "or_cleaning"): {"actions": {"mark_cleaned"}, "scope": "all", "fields": []},
    ("patient", "patient_record"): {"actions": {"read"}, "scope": "own",
                                    "fields": ["patient_id", "name", "dob", "diagnosis", "medications", "allergies"]},
    ("patient", "lab_results"): {"actions": {"read"}, "scope": "own",
                                 "fields": ["result_id", "test", "value", "flag", "status"]},
}

# Emergency override: these roles may read these resources outside their normal scope, with a written reason.
BREAK_GLASS = {("doctor", "patient_record"), ("doctor", "lab_results"), ("nurse", "patient_record"), ("nurse", "lab_results")}
MIN_REASON_CHARS = 10
