import re
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SKILL = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8") if (SKILL_DIR / "SKILL.md").exists() else ""
SETUP = (SKILL_DIR / "SETUP.md").read_text(encoding="utf-8") if (SKILL_DIR / "SETUP.md").exists() else ""


def cli_commands():
    out = subprocess.run([sys.executable, str(SKILL_DIR / "scripts" / "smc.py"), "--help"],
                         capture_output=True, text=True).stdout
    return set(re.search(r"\{([a-z,-]+)\}", out).group(1).split(","))


def test_frontmatter():
    assert SKILL.startswith("---\n")
    front = SKILL.split("---")[1]
    assert "name: smc-forex-alerts" in front
    assert re.search(r"description: \S+", front)


def test_referenced_files_exist():
    paths = set(re.findall(r"(references/[\w-]+\.md|scripts/[\w-]+\.py)", SKILL))
    assert paths, "SKILL.md should reference its guides and CLI"
    for p in paths:
        assert (SKILL_DIR / p).exists(), p


def test_cli_commands_exist():
    known = cli_commands()
    docs = [SKILL] + [p.read_text(encoding="utf-8") for p in (SKILL_DIR / "references").glob("*.md")]
    used = {m for text in docs for m in re.findall(r"smc\.py(?: --\S+ \S+)* ([a-z][a-z-]+)", text)}
    assert used, "docs should show smc.py commands"
    assert used <= known, used - known


def test_hard_rules_present():
    assert "Paper Trading" in SKILL
    assert re.search(r"never[^\n]*real", SKILL, re.I)
    assert "unreadable" in SKILL


def test_setup_mentions():
    for needle in ["SMC Scanner", "Remote Control", "paper_until", "not financial advice"]:
        assert needle in SETUP, needle
