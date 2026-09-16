"""A small seeded fake EHR dataset, keyed by name + DOB, for the intake
'EHR match found' toggle. Pure simulation — no real patient data."""

FAKE_EHR = [
    {
        "name": "Maria Gonzalez", "dob": "1958-03-14", "age": 68, "sex": "F",
        "known_conditions": ["Type 2 diabetes", "Hypertension"],
        "medications": ["Metformin", "Lisinopril"],
        "prior_ed_visits": 3,
        "last_vitals_trend": "worsening",
    },
    {
        "name": "James Okafor", "dob": "1990-07-02", "age": 35, "sex": "M",
        "known_conditions": ["Asthma"],
        "medications": ["Albuterol inhaler"],
        "prior_ed_visits": 1,
        "last_vitals_trend": "stable",
    },
    {
        "name": "Wei Chen", "dob": "1975-11-23", "age": 50, "sex": "M",
        "known_conditions": ["Coronary artery disease", "High cholesterol"],
        "medications": ["Atorvastatin", "Aspirin"],
        "prior_ed_visits": 5,
        "last_vitals_trend": "worsening",
    },
    {
        "name": "Aisha Bello", "dob": "1999-01-09", "age": 27, "sex": "F",
        "known_conditions": [],
        "medications": [],
        "prior_ed_visits": 0,
        "last_vitals_trend": "stable",
    },
    {
        "name": "Robert Klein", "dob": "1949-09-30", "age": 76, "sex": "M",
        "known_conditions": ["COPD", "Atrial fibrillation"],
        "medications": ["Warfarin", "Tiotropium"],
        "prior_ed_visits": 4,
        "last_vitals_trend": "worsening",
    },
    {
        "name": "Priya Nair", "dob": "2003-05-17", "age": 22, "sex": "F",
        "known_conditions": ["Migraine disorder"],
        "medications": ["Sumatriptan"],
        "prior_ed_visits": 2,
        "last_vitals_trend": "stable",
    },
    {
        "name": "Tomas Novak", "dob": "1965-12-01", "age": 60, "sex": "M",
        "known_conditions": ["Chronic kidney disease"],
        "medications": ["Furosemide"],
        "prior_ed_visits": 2,
        "last_vitals_trend": "improving",
    },
    {
        "name": "Grace Kim", "dob": "2016-04-08", "age": 9, "sex": "F",
        "known_conditions": ["Peanut allergy"],
        "medications": ["Epinephrine auto-injector (as needed)"],
        "prior_ed_visits": 1,
        "last_vitals_trend": "stable",
    },
]


def find_ehr_match(name: str, dob: str = None):
    name_l = (name or "").strip().lower()
    for rec in FAKE_EHR:
        if rec["name"].strip().lower() == name_l:
            if dob and rec["dob"] != dob:
                continue
            return rec
    return None
