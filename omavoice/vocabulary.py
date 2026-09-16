"""Correct the words whisper reliably mishears.

The usual way to teach whisper a word is an initial prompt, but a prompt only
reaches the decoder through its text context, and text context is what makes
whisper loop. Measured on a 91-minute meetup recording: with no context the
prompt is ignored outright, and every context budget that let it through fixed
some mishearings and missed others while reopening the loop risk.

So vocabulary is fixed after decoding instead. Each term lists the ways it
actually comes out, and those are rewritten to the term that was meant. A term
also normalises its own spelling, so "github" comes out as "GitHub". Matching
is whole words only, case-insensitive, and never inside a domain, a path or a
hyphenated word; the longest match wins so a phrase beats a word inside it.

A variant belongs here only if it is not an ordinary word in its own right.
"pseudo" is how whisper hears sudo, but people say pseudo; "cloud" is how it
hears Claude, but people say cloud; "quick shell", "fast fetch" and "flat pack"
are ordinary phrases too. Those are left alone on purpose.
"""

import re

OMARCHY = {
    "Omarchy": [
        "Omaki", "Omarchi", "Omarchie", "Omarchic", "Omachi", "Omachy", "Omarze",
        "Omarky", "Omarkey", "O'Marchy", "O Marchy", "Amarty",
    ],
    "Hyprland": ["Hyperland", "Hyper land", "Hyperlands"],
    "Waybar": ["Way bar"],
    "Quickshell": [],
}

LINUX = {
    "Linux": ["Linox", "Linucks"],
    "Arch Linux": ["Arch Linox"],
    "Ubuntu": ["Ubunto", "Oobuntu", "Uboontu"],
    "Debian": [],
    "NixOS": ["Nix OS", "Nicks OS"],
    "Wayland": ["Way land"],
    "PipeWire": ["Pipe wire", "Pipewire"],
    "PulseAudio": ["Pulse audio"],
    "systemd": ["System D", "SystemD"],
    "sudo": [],
    "pacman": ["Pac-Man", "Pacman"],
    "AUR": ["A U R", "A.U.R."],
    "tmux": ["T mux", "Tee mux", "Teamux"],
    "btop": ["B top", "Bee top"],
    "fastfetch": [],
    "neofetch": ["Neo fetch"],
    "Btrfs": ["Butter FS", "Butter F S", "ButterFS"],
    "Alacritty": ["Alacrity", "Alacritie"],
    "Ghostty": ["Ghosty"],
    "KDE": [],
    "Flatpak": [],
}

TECH = {
    "GitHub": ["Git hub", "Get hub", "Github"],
    "GitLab": ["Git lab", "Gitlab"],
    "Kubernetes": ["Cooper Netties", "Kuber Nettes", "Kubernetties", "Kubernettes"],
    "YAML": ["Yamel"],
    "Nginx": ["Engine X", "Engine-X", "EngineX"],
    "Postgres": ["Post Gres", "Postgress"],
    "SQLite": ["Sequel light", "SQL light", "Sequel lite"],
    "Ollama": ["Olama", "Olamma"],
    "Tailscale": ["Tail scale", "Tailscail"],
    "Cloudflare": ["Cloud flare"],
    "Vercel": ["Versel"],
    "Neovim": ["Neo vim", "Neovim", "NeoVim"],
    "VS Code": ["V S Code", "VSCode", "VS code"],
    "TypeScript": ["Type script", "Typescript"],
    "JavaScript": ["Java script", "Javascript"],
    "npm": ["N P M"],
    "API": [],
    "CPU": [],
    "GPU": [],
    "SSD": [],
    "SSH": [],
    "NVMe": ["N V M E", "NVME"],
    "NVIDIA": [],
    "LLM": ["L L M"],
    "macOS": ["Mac OS", "MacOS"],
}

DEFAULT_VOCABULARY = {**TECH, **LINUX, **OMARCHY}


def _clean(vocabulary) -> dict:
    """Keep only well-formed entries: a string term mapped to strings."""
    clean = {}
    if not isinstance(vocabulary, dict):
        return clean
    for term, heard in vocabulary.items():
        if not isinstance(term, str) or not term.strip() or not isinstance(heard, list):
            continue
        clean[term.strip()] = [h for h in heard if isinstance(h, str) and h.strip()]
    return clean


class Corrector:
    def __init__(self, user_vocabulary=None):
        merged = {term: list(heard) for term, heard in DEFAULT_VOCABULARY.items()}
        for term, heard in _clean(user_vocabulary).items():
            merged.setdefault(term, []).extend(heard)
        self._replacement = {}
        for term, heard in merged.items():
            # The term itself, so its spelling is normalised too.
            for variant in [term, *heard]:
                key = re.sub(r"\s+", " ", variant.strip().lower())
                if key:
                    self._replacement[key] = term
        # Longest first, so "omarchi.nickstread.com" is rewritten as a whole
        # before "omarchi" on its own gets the chance.
        alternatives = sorted(self._replacement, key=len, reverse=True)
        body = "|".join(r"\s+".join(map(re.escape, v.split())) for v in alternatives)
        # Not inside a word, a domain, a path or a hyphenation: nothing touching
        # the match on either side that would make it part of something bigger.
        self._pattern = re.compile(rf"(?<![\w'./@-])(?:{body})(?![\w'/@-]|\.\w)", re.IGNORECASE)

    def apply(self, text: str) -> str:
        if not text:
            return text
        return self._pattern.sub(self._replace, text)

    def _replace(self, match) -> str:
        key = re.sub(r"\s+", " ", match.group(0).lower())
        return self._replacement.get(key, match.group(0))
