"""Immutable packaged prompts; selection is operator configuration, never user input."""

import hashlib
from dataclasses import dataclass
from importlib.resources import files


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    text: str

    @property
    def sha256(self):
        return hashlib.sha256(self.text.encode()).hexdigest()


def load_prompt(name, version="v1"):
    if name not in {"planner", "specialist", "supervisor", "judge"} or version != "v1":
        raise ValueError("Unknown packaged prompt version")
    text = files("jev_core").joinpath(f"prompts/{name}.{version}.txt").read_text()
    return Prompt(name, version, text.strip())
