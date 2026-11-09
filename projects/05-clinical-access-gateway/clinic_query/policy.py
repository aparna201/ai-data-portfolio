"""Who may see what: role -> table -> allowed columns. Anything not listed is denied."""

POLICY: dict[str, dict[str, list[str]]] = {
    "front_desk": {
        "patients": ["patient_id", "name", "phone"],
        "appointments": ["appt_id", "patient_id", "doctor", "appt_date", "status"],
    },
    "doctor": {
        "patients": ["patient_id", "name", "city"],
        "appointments": ["appt_id", "patient_id", "doctor", "appt_date", "status"],
    },
    "billing": {
        "patients": ["patient_id", "name"],
        "invoices": ["invoice_id", "patient_id", "amount", "status"],
    },
}
