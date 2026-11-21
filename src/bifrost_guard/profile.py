"""A project's Profile and the fingerprints of the accepted rules (Law Rule 1)."""
from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

LAW_PATH = Path(__file__).resolve().parent / "LAW.md"


@dataclass
class Harm:
    code: str
    title: str
    meaning: str


@dataclass
class Profile:
    name: str
    version: str
    repo: Path
    harms: list[Harm]
    notes: list[str]
    conditions: list[str]
    choices: list[str]
    pinned_files: list[str]            # files in the repo covered by the fingerprint (Rule 1)
    known_problems: str | None          # one of pinned_files
    reviewed_packages: list[str]        # code that a test may not replace (Rule 13)
    allowed_stand_ins: list[str]        # outside world a test may replace (Rule 13)
    test_command: str                   # {python} and {test} are filled in
    python: str
    runs: int = 5
    run_timeout_s: int = 300
    no_network: bool = True
    judges: list[dict] = field(default_factory=list)
    source: Path | None = None

    def harm(self, code: str) -> Harm | None:
        return next((h for h in self.harms if h.code.upper() == (code or "").strip().upper()), None)


def load_profile(path: str | Path) -> Profile:
    path = Path(path).resolve()
    d = yaml.safe_load(path.read_text())
    repo = Path(d["repo"])
    if not repo.is_absolute():
        repo = (path.parent / repo).resolve()
    mc = d.get("machine_check", {})
    return Profile(
        name=d["name"], version=str(d["version"]), repo=repo,
        harms=[Harm(h["code"], h["title"], h["meaning"]) for h in d["harms"]],
        notes=d.get("notes", []), conditions=d.get("operating_conditions", []),
        choices=d.get("owner_choices", []),
        pinned_files=d.get("pinned_files", []), known_problems=d.get("known_problems"),
        reviewed_packages=mc.get("reviewed_packages", []),
        allowed_stand_ins=mc.get("allowed_stand_ins", []),
        test_command=mc.get("test_command", "{python} -m pytest -q -p no:cacheprovider {test}"),
        python=mc.get("python", "python3"), runs=int(mc.get("runs", 5)),
        run_timeout_s=int(mc.get("run_timeout_s", 300)), no_network=bool(mc.get("no_network", True)),
        judges=d.get("judges", []), source=path,
    )


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_show(repo: Path, commit: str, rel: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), "show", f"{commit}:{rel}"],
                          check=True, capture_output=True).stdout


def resolve_commit(repo: Path, ref: str) -> str:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", f"{ref}^{{commit}}"],
                          check=True, capture_output=True, text=True).stdout.strip()


def fingerprints(profile: Profile, commit: str) -> dict[str, str]:
    """The Law, the Profile, and each pinned file as it is at `commit`."""
    out = {"law": _sha(LAW_PATH.read_bytes()), "profile": _sha(profile.source.read_bytes())}
    for rel in profile.pinned_files:
        out[rel] = _sha(git_show(profile.repo, commit, rel))
    combined = "\n".join(f"{k}={v}" for k, v in sorted(out.items()))
    out["all"] = _sha(combined.encode())
    return out
