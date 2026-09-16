"""
Complaint-text matching, upgraded from literal substring checks to a
lightweight local fuzzy matcher, so typos and reordered phrasing still
match — "pain in my chest" and "crushing chest pian" should both trigger
the same red flag as "chest pain" does today.

Design note, including a bug found and fixed during testing: the first
version of this used whole-phrase character n-gram TF-IDF cosine
similarity. That caught typos well but produced real false positives —
"sore throat" (tier 5, routine) fuzzy-matched "throat swelling" (tier 1,
critical) at 0.70 similarity purely because both strings contain the word
"throat"; separately, "not feeling well" matched "swelling" via
coincidental character overlap between "feeling" and "swelling". Whole-
string similarity can't tell "these share a topic word" apart from "these
mean the same thing."

The fix: match per-word, and require ALL of a phrase's words to have a
fuzzy match among the complaint's tokens, not just overall string overlap.
"throat swelling" now correctly requires both a "throat"-ish word AND a
"swelling"-ish word to be present — "sore throat" has the former but not
the latter, so it no longer collides. Per-word matching uses difflib's
sequence ratio rather than character n-grams, because it handles the most
common real typo pattern (adjacent-letter transposition, e.g. "pian" for
"pain") much better than fixed-length n-grams do — n-grams break on a
transposition since most of the n-grams spanning the swap change, while
sequence-ratio still finds the long common subsequence either side of it.

Still fully local — no API calls, no downloaded model weights.
"""
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, List, Tuple

# A small set of common shorthand/synonym expansions a triage nurse might
# actually type. Cheap and catches cases word-similarity alone would miss
# (abbreviations don't resemble the spelled-out term letter-for-letter).
SYNONYM_EXPANSIONS = {
    r"\bsob\b": "shortness of breath",
    r"\bcp\b": "chest pain",
    r"\bloc\b": "loss of consciousness unconscious",
    r"\bafib\b": "atrial fibrillation irregular heartbeat",
    r"\bmi\b": "heart attack myocardial infarction chest pain",
    r"\bcva\b": "stroke",
    r"\bsvt\b": "rapid heartbeat",
    r"\bgsw\b": "gunshot wound severe bleeding trauma",
    r"\bn/v\b": "nausea vomiting",
    r"\bab pain\b": "abdominal pain",
    r"\bpt\b": "patient",
    r"\bhurts?\b": "pain",
    r"\baching\b": "pain",
    r"\bcan't move\b": "weakness",
}

WORD_SIMILARITY_THRESHOLD = 0.72
_WORD_RE = re.compile(r"[a-z0-9']+")

# Short filler/function words are excluded as phrase-word anchors are fine
# to match against them, but we never want a filler word in the *complaint*
# spuriously satisfying a real clinical phrase word — in practice this
# matters less with the require-all-words design, but keeping short common
# words out of consideration avoids e.g. "a" matching everything.
_MIN_WORD_LEN_FOR_FUZZY = 3


def _expand_synonyms(text: str) -> str:
    out = text.lower()
    for pattern, expansion in SYNONYM_EXPANSIONS.items():
        out = re.sub(pattern, expansion, out)
    return out


def _word_sim(a: str, b: str) -> float:
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


@dataclass
class PhraseMatch:
    phrase: str
    tier: int
    similarity: float


class ComplaintMatcher:
    """Matches free-text complaints against a canonical phrase bank. A
    phrase matches if every one of its words has a fuzzy match among the
    complaint's tokens (order-independent, so reordering is naturally
    tolerated); the match's similarity is the weakest per-word match,
    since a phrase is only as good as its least-confident word."""

    def __init__(self, phrase_tiers: Dict[str, int]):
        self.tiers = phrase_tiers
        self.phrase_words = {phrase: phrase.split() for phrase in phrase_tiers}

    def match(self, text: str, threshold: float = WORD_SIMILARITY_THRESHOLD) -> List[PhraseMatch]:
        expanded = _expand_synonyms(text or "")
        if not expanded.strip():
            return []

        tokens = _WORD_RE.findall(expanded)
        if not tokens:
            return []

        results: List[PhraseMatch] = []

        # Fast path: exact substring match on the (synonym-expanded) text,
        # always counted at similarity 1.0.
        for phrase, tier in self.tiers.items():
            if phrase in expanded:
                results.append(PhraseMatch(phrase, tier, 1.0))
        already = {r.phrase for r in results}

        # Fuzzy path: every word in the phrase needs a fuzzy match among
        # the complaint's tokens.
        for phrase, tier in self.tiers.items():
            if phrase in already:
                continue
            words = self.phrase_words[phrase]
            per_word_best = []
            ok = True
            for w in words:
                if len(w) < _MIN_WORD_LEN_FOR_FUZZY:
                    # Very short phrase words (rare in our bank) require an
                    # exact token match rather than fuzzy — fuzzy matching
                    # 2-letter words against everything is just noise.
                    best = 1.0 if w in tokens else 0.0
                else:
                    best = max((_word_sim(w, t) for t in tokens), default=0.0)
                if best < threshold:
                    ok = False
                    break
                per_word_best.append(best)
            if ok and per_word_best:
                results.append(PhraseMatch(phrase, tier, min(per_word_best)))

        return results

    def best_tier(self, text: str) -> Tuple[int, List[PhraseMatch]]:
        matches = self.match(text)
        if not matches:
            return None, []
        best = min(matches, key=lambda m: m.tier)
        return best.tier, matches
