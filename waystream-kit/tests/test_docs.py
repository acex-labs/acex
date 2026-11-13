import re

import pytest

from ibos_kit import evidence
from ibos_kit.mock.scenarios import SCENARIOS
from ibos_kit.paths import DOCS, KIT_ROOT

CUSTOMER = "".join(["we", "x", "net"])
SECRET_SHAPES = (
    r"-----BEGIN [A-Z ]*PRIVATE KEY",
    r"ghp_[A-Za-z0-9]{20,}",
    r"ATATT[A-Za-z0-9]{10,}",
    r"AKIA[0-9A-Z]{16}",
    r"eyJ[A-Za-z0-9_-]{20,}\.",
    r"xox[abp]-[A-Za-z0-9-]{10,}",
)


def kit_files():
    skip = {".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
    return [
        p
        for p in KIT_ROOT.rglob("*")
        if p.is_file() and not skip & set(p.relative_to(KIT_ROOT).parts) and p.suffix != ".pyc"
    ]


def test_the_evidence_matrix_is_what_the_register_generates():
    assert (DOCS / "evidence.md").read_text() == evidence.render_matrix()


def test_the_register_is_internally_consistent():
    assert evidence.load().problems() == []


def test_the_checklist_names_every_fact_that_is_not_verified():
    checklist = (DOCS / "real-device-checklist.md").read_text()
    missing = [f.id for f in evidence.load().facts.values() if f.level != "VERIFIED" and f"`{f.id}`" not in checklist]
    assert missing == []


def test_every_fact_id_named_in_the_docs_exists():
    known = set(evidence.load().facts)
    for name in ("guide.md", "exercises.md", "real-device-checklist.md", "architecture.md", "limitations.md"):
        text = (DOCS / name).read_text()
        cited = set(re.findall(r"`([A-Z][A-Z0-9]+(?:-[A-Z0-9]+)+)`", text))
        assert cited <= known, (name, cited - known)


def test_the_exercises_are_all_there_in_order():
    headings = re.findall(r"^## Exercise (\d): ", (DOCS / "exercises.md").read_text(), re.MULTILINE)
    assert headings == [str(n) for n in range(1, 9)]


def test_every_exercise_has_a_test_file_the_docs_name():
    text = (DOCS / "exercises.md").read_text()
    for path in sorted((KIT_ROOT / "exercise" / "tests").glob("test_ex*.py")):
        assert path.name in text or path.name == "test_ex1_environment.py", path.name


def test_every_scenario_in_the_readme_exists_and_every_scenario_is_in_the_readme():
    readme = (KIT_ROOT / "README.md").read_text()
    named = set(re.findall(r"^\| `([a-f]-[\w-]+)` \|", readme, re.MULTILINE))
    assert named == {key for key in SCENARIOS if key[0] in "abcdef"}


@pytest.mark.parametrize("name", ["README.md", *[f"docs/{p.name}" for p in DOCS.glob("*.md")]])
def test_relative_links_in_the_docs_resolve(name):
    path = KIT_ROOT / name
    for target in re.findall(r"\]\((?!https?://|#)([^)#]+)", path.read_text()):
        assert (path.parent / target).resolve().exists(), f"{name}: {target}"


def test_the_customer_is_not_named_anywhere_in_the_kit():
    offenders = [str(p.relative_to(KIT_ROOT)) for p in kit_files() if CUSTOMER in p.read_text(errors="ignore").lower()]
    assert offenders == []


def test_no_file_in_the_kit_looks_like_it_holds_a_credential():
    offenders = [
        str(p.relative_to(KIT_ROOT))
        for p in kit_files()
        if any(re.search(shape, p.read_text(errors="ignore")) for shape in SECRET_SHAPES)
    ]
    assert offenders == []


def test_no_host_key_or_known_hosts_file_is_written_by_the_kit():
    names = {p.name for p in kit_files()}
    assert not names & {"known_hosts", "id_rsa", "id_ed25519", "ssh_host_ed25519_key", "mock_host_key"}


def test_the_kit_never_touches_the_ssh_directory_of_the_user():
    for path in (KIT_ROOT / "src").rglob("*.py"):
        assert ".ssh" not in path.read_text(), path
