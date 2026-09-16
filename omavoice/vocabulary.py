"""Correct the words whisper reliably mishears.

The usual way to teach whisper a word is an initial prompt, but a prompt only
reaches the decoder through its text context, and text context is what makes
whisper loop. Measured on a 91-minute meetup recording: with no context the
prompt is ignored outright, and every context budget that let it through fixed
some mishearings and missed others while reopening the loop risk.

So vocabulary is fixed after decoding instead. Each term lists the ways it
actually comes out, and those are rewritten to the term that was meant: whole
words only, case-insensitive, longest match first so a phrase wins over a word
inside it.
"""

import re

# Terms for the platform Omavoice is built for. Personal vocabulary (names,
# domains, projects) belongs in the user's config, not here.
DEFAULT_VOCABULARY = {
    "Omarchy": [
        "Omaki", "Omarchi", "Omarchie", "Omachi", "Omachy", "Omarze", "Omarky",
        "Omarkey", "O'Marchy", "O Marchy", "Amarty",
    ],
    "Hyprland": ["Hyperland", "Hyper land", "Hyperlands"],
}


def _clean(vocabulary) -> dict:
    """Keep only well-formed entries: a string term mapped to strings."""
    clean = {}
    if not isinstance(vocabulary, dict):
        return clean
    for term, heard in vocabulary.items():
        if not isinstance(term, str) or not term.strip() or not isinstance(heard, list):
            continue
        variants = [h for h in heard if isinstance(h, str) and h.strip()]
        if variants:
            clean[term.strip()] = variants
    return clean


class Corrector:
    def __init__(self, user_vocabulary=None):
        merged = {term: list(heard) for term, heard in DEFAULT_VOCABULARY.items()}
        for term, heard in _clean(user_vocabulary).items():
            merged.setdefault(term, []).extend(heard)
        self._replacement = {}
        for term, heard in merged.items():
            for variant in heard:
                if variant.strip().lower() != term.lower():
                    self._replacement[variant.strip().lower()] = term
        if not self._replacement:
            self._pattern = None
            return
        # Longest first, so "omarchi.nickstread.com" is rewritten as a whole
        # before "omarchi" on its own gets the chance.
        alternatives = sorted(self._replacement, key=len, reverse=True)
        body = "|".join(r"\s+".join(map(re.escape, v.split())) for v in alternatives)
        self._pattern = re.compile(rf"(?<![\w'])(?:{body})(?![\w'])", re.IGNORECASE)

    def apply(self, text: str) -> str:
        if not text or self._pattern is None:
            return text
        return self._pattern.sub(self._replace, text)

    def _replace(self, match) -> str:
        key = re.sub(r"\s+", " ", match.group(0).lower())
        return self._replacement.get(key, match.group(0))
