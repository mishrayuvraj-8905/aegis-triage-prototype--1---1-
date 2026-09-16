"""Canonical complaint phrase banks. Lives in its own module (rather than
inside scoring.py) so both the rules engine and the ML feature extractor can
import the same phrase list without a circular import between them."""

RED_FLAG_TERMS = {
    "chest pain": 1,
    "crushing chest": 1,
    "difficulty breathing": 1,
    "can't breathe": 1,
    "cannot breathe": 1,
    "shortness of breath": 2,
    "unconscious": 1,
    "unresponsive": 1,
    "stroke": 1,
    "face drooping": 1,
    "slurred speech": 1,
    "one-sided weakness": 1,
    "severe bleeding": 1,
    "uncontrolled bleeding": 1,
    "hemorrhage": 1,
    "seizure": 2,
    "anaphylaxis": 1,
    "allergic reaction": 2,
    "hives": 2,
    "facial swelling": 1,
    "throat swelling": 1,
    "swelling": 3,
    "overdose": 1,
    "suicidal": 2,
    "severe pain": 2,
    "head injury": 2,
    "high fever": 3,
}

MODERATE_TERMS = {
    "abdominal pain": 3,
    "vomiting": 3,
    "dizziness": 3,
    "fall": 3,
    "laceration": 3,
    "fracture": 3,
    "possible fracture": 3,
    "migraine": 3,
    "headache": 3,
    "back pain": 4,
    "sprain": 4,
    "rash": 4,
    "cold symptoms": 5,
    "sore throat": 5,
    "cough": 4,
    "minor cut": 5,
    "medication refill": 5,
    "follow-up": 5,
}

VAGUE_COMPLAINT_MARKERS = ["not feeling well", "feels off", "unwell", "tired", "weak", "not right", ""]

# Staged-action order sets: when a red-flag category fires on a tier <=2
# case, these are the order sets a nurse would typically want drafted and
# ready to one-click-confirm, rather than having to build them from scratch.
# This does NOT auto-order anything — it's a suggestion the nurse still has
# to confirm, same as the tier itself.
ORDER_SET_TRIGGERS = {
    "cardiac": {
        "phrases": ["chest pain", "crushing chest"],
        "orders": ["12-lead ECG", "Troponin + cardiac panel", "IV access", "Continuous cardiac monitoring"],
    },
    "respiratory": {
        "phrases": ["difficulty breathing", "can't breathe", "cannot breathe", "shortness of breath"],
        "orders": ["Pulse oximetry + continuous monitoring", "Chest X-ray", "ABG", "Supplemental O2 per protocol"],
    },
    "neuro": {
        "phrases": ["stroke", "face drooping", "slurred speech", "one-sided weakness"],
        "orders": ["Stroke protocol activation", "STAT CT head", "Glucose check", "Neuro checks q15min"],
    },
    "anaphylaxis": {
        "phrases": ["anaphylaxis", "allergic reaction", "hives", "facial swelling", "throat swelling"],
        "orders": ["Epinephrine per protocol", "IV antihistamine + steroid", "Continuous monitoring", "Airway equipment at bedside"],
    },
    "hemorrhage": {
        "phrases": ["severe bleeding", "uncontrolled bleeding", "hemorrhage"],
        "orders": ["Type & screen / crossmatch", "Large-bore IV access x2", "CBC + coags", "Direct pressure / hemostatic dressing"],
    },
    "trauma": {
        "phrases": ["head injury", "fracture", "fall"],
        "orders": ["Imaging (CT/X-ray per site)", "IV access", "Pain control per protocol"],
    },
    "seizure": {
        "phrases": ["seizure"],
        "orders": ["IV access", "Glucose + electrolyte panel", "Continuous monitoring", "Seizure precautions"],
    },
    "overdose": {
        "phrases": ["overdose"],
        "orders": ["Toxicology panel", "IV access", "Continuous monitoring", "Poison control consult"],
    },
}
