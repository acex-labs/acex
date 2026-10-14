"""Changelog fragments: one file per change, written by the author, stamped with the
version when the release is cut. Nobody edits a shared file and nobody types a version."""

import json
import subprocess
from datetime import date
from pathlib import Path

import pytest
from acex.changelog import tool

PYPROJECT = """[tool.poetry]
name = "acex-driver-example"
version = "1.2.3"
description = "ACE-X Driver: Example"
packages = [{ include = "acex_driver_example", from = "src" }]

[tool.acex.changelog]
name = "Example driver"
"""


def write_fragment(path: Path, *, kind="added", title="Devices can be adopted", body="Longer text.", **fields):
    lines = [f"kind: {kind}", f"title: {title}", *(f"{key}: {value}" for key, value in fields.items())]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + "\n".join(lines) + "\n---\n" + body + "\n", encoding="utf-8")
    return path


def write_coming(path: Path, *, title="Junos ZTP", **fields):
    lines = [f"title: {title}", *(f"{key}: {value}" for key, value in fields.items())]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + "\n".join(lines) + "\n---\nPlanned.\n", encoding="utf-8")
    return path


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "drivers" / "example"
    (root / "src" / "acex_driver_example").mkdir(parents=True)
    (root / "changelog.d").mkdir()
    (root / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    return tmp_path


@pytest.fixture
def component(repo):
    [component] = tool.discover(repo)
    return component


class TestDiscovery:
    def should_find_a_package_by_its_fragment_directory(self, repo, component):
        assert (component.id, component.name, component.version) == ("acex-driver-example", "Example driver", "1.2.3")
        assert component.output == repo / "drivers/example/src/acex_driver_example/changelog.json"

    def should_ignore_directories_without_a_pyproject_and_hidden_ones(self, repo):
        (repo / "docs" / "changelog.d").mkdir(parents=True)
        (repo / ".venv" / "lib" / "changelog.d").mkdir(parents=True)
        (repo / ".venv" / "lib" / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
        assert [c.id for c in tool.discover(repo)] == ["acex-driver-example"]

    def should_name_a_component_after_its_package_without_a_display_name(self, repo):
        (repo / "drivers/example/pyproject.toml").write_text(PYPROJECT.split("[tool.acex")[0], encoding="utf-8")
        [component] = tool.discover(repo)
        assert component.name == "acex-driver-example"

    def should_find_a_component_by_id_or_directory(self, repo, component):
        assert tool.find([component], "acex-driver-example") is component
        assert tool.find([component], "example") is component
        with pytest.raises(tool.FragmentError, match="No component 'other'"):
            tool.find([component], "other")


class TestFragments:
    def should_read_every_field(self, component):
        path = write_fragment(
            component.fragments_dir / "20261013-adopt.md",
            breaking="true",
            audience="admin",
            refs="#316, ADO-1234 https://dev.azure.com/x/_workitems/edit/1234, https://github.com/acex-labs/acex/pull/9",
            completes="adoption",
        )
        entry = tool.parse_fragment(path)
        assert entry == {
            "id": "20261013-adopt",
            "kind": "added",
            "title": "Devices can be adopted",
            "description": "Longer text.",
            "breaking": True,
            "audience": "admin",
            "refs": [
                {"label": "#316", "url": None},
                {"label": "ADO-1234", "url": "https://dev.azure.com/x/_workitems/edit/1234"},
                {"label": "9", "url": "https://github.com/acex-labs/acex/pull/9"},
            ],
            "completes": "adoption",
        }

    def should_default_what_is_left_out(self, component):
        entry = tool.parse_fragment(write_fragment(component.fragments_dir / "x.md", body=""))
        assert (entry["description"], entry["breaking"], entry["audience"], entry["refs"]) == (None, False, "user", [])

    @pytest.mark.parametrize(
        ("written", "expected"),
        [
            ('Accepts "init"', 'Accepts "init"'),
            ('"Quoted" is the first word', '"Quoted" is the first word'),
            ('"Wrapped in quotes"', "Wrapped in quotes"),
            ("'Single quoted'", "Single quoted"),
            ("Don't lose the apostrophe's", "Don't lose the apostrophe's"),
        ],
    )
    def should_only_remove_quotes_that_wrap_the_whole_value(self, component, written, expected):
        path = write_fragment(component.fragments_dir / "q.md", title=written)
        assert tool.parse_fragment(path)["title"] == expected

    @pytest.mark.parametrize(
        ("content", "problem"),
        [
            ("kind: added\ntitle: No markers\n", "front matter"),
            ("---\nkind: added\n---\n", "'title' is required"),
            ("---\nkind: added\ntitle: " + "x" * 81 + "\n---\n", "keep it under 80"),
            ("---\nkind: added\ntitle: Feat/ztp backend\n---\n", "commit subject or branch name"),
            ("---\nkind: added\ntitle: fix: NodeService.update test\n---\n", "commit subject or branch name"),
            ("---\nkind: feature\ntitle: Fine\n---\n", "'kind' must be one of"),
            ("---\nkind: added\ntitle: Fine\nbreaking: maybe\n---\n", "'breaking' must be true or false"),
            ("---\nkind: added\ntitle: Fine\nversion: 1.0\n---\n", "unknown front matter field.s.: version"),
            ("---\nkind: added\ntitle: Fine\nnot a field\n---\n", "expected 'key: value'"),
        ],
    )
    def should_refuse_what_users_would_not_understand(self, component, content, problem):
        path = component.fragments_dir / "bad.md"
        path.write_text(content, encoding="utf-8")
        with pytest.raises(tool.FragmentError, match=problem):
            tool.parse_fragment(path)

    def should_leave_the_readme_alone(self, component):
        (component.fragments_dir / "README.md").write_text("# How to\n", encoding="utf-8")
        assert tool.fragments(component) == []

    def should_publish_breaking_first_then_by_kind_and_title(self, component):
        write_fragment(component.fragments_dir / "a.md", kind="fixed", title="Zebra")
        write_fragment(component.fragments_dir / "b.md", kind="added", title="Yak")
        write_fragment(component.fragments_dir / "c.md", kind="fixed", title="Apple", breaking="true")
        write_fragment(component.fragments_dir / "d.md", kind="internal", title="Ruff format")
        titles = [e["title"] for e in tool.published(tool.fragments(component))]
        assert titles == ["Apple", "Yak", "Zebra"]
        assert "completes" not in tool.published(tool.fragments(component))[0]


class TestNew:
    def should_create_a_file_nobody_else_will_pick(self, component):
        path = tool.new_fragment(component, kind="fixed", title="Interfaces keep their description")
        assert path.name == f"{date.today():%Y%m%d}-interfaces-keep-their-description.md"
        assert tool.parse_fragment(path)["kind"] == "fixed"
        with pytest.raises(tool.FragmentError, match="already exists"):
            tool.new_fragment(component, kind="fixed", title="Interfaces keep their description")


class TestRelease:
    def should_stamp_the_version_and_date_and_consume_the_fragments(self, component):
        write_fragment(component.fragments_dir / "a.md", kind="fixed", title="Zebra")
        write_fragment(component.fragments_dir / "b.md", kind="added", title="Yak")

        report = tool.release(component, on=date(2026, 10, 20))

        assert report.ok, report.errors
        data = json.loads(component.output.read_text(encoding="utf-8"))
        assert data["component"] == "acex-driver-example"
        assert data["name"] == "Example driver"
        [release] = data["releases"]
        assert (release["version"], release["date"]) == ("1.2.3", "2026-10-20")
        assert [e["title"] for e in release["entries"]] == ["Yak", "Zebra"]
        assert list(component.fragments_dir.glob("*.md")) == []

    def should_store_the_summary_of_a_release_above_its_entries(self, component):
        write_fragment(component.fragments_dir / "a.md")

        report = tool.release(component, on=date(2026, 10, 20), summary="ZTP arrives for Cisco   switches.")

        assert report.ok, report.errors
        [release] = json.loads(component.output.read_text(encoding="utf-8"))["releases"]
        assert release["summary"] == "ZTP arrives for Cisco switches."  # whitespace is tidied
        assert list(release) == ["version", "date", "summary", "entries"]

    def should_leave_the_summary_out_when_none_is_given(self, component):
        write_fragment(component.fragments_dir / "a.md")
        assert tool.release(component).ok
        [release] = json.loads(component.output.read_text(encoding="utf-8"))["releases"]
        assert "summary" not in release

    def should_refuse_a_summary_that_is_not_one_sentence_long(self, component):
        write_fragment(component.fragments_dir / "a.md")

        report = tool.release(component, summary="x" * 201)

        assert "keep it under 200" in report.errors[0]
        assert len(list(component.fragments_dir.glob("*.md"))) == 1  # nothing consumed

    def should_say_when_a_summary_has_nothing_to_summarise(self, component):
        write_fragment(component.fragments_dir / "a.md", kind="internal", title="Pinned scrapli")
        report = tool.release(component, summary="Nothing users can see.")
        assert report.ok and any("summary was not stored" in n for n in report.notes)

    def should_refuse_to_release_a_version_twice(self, component):
        write_fragment(component.fragments_dir / "a.md")
        assert tool.release(component).ok
        write_fragment(component.fragments_dir / "b.md")

        report = tool.release(component)

        assert any("1.2.3 is already in" in e for e in report.errors)
        assert len(list(component.fragments_dir.glob("*.md"))) == 1  # nothing consumed

    def should_bump_the_package_version_when_asked(self, component):
        write_fragment(component.fragments_dir / "a.md")
        tool.release(component)
        write_fragment(component.fragments_dir / "b.md", kind="fixed", title="Later")

        report = tool.release(component, bump_how="minor")

        assert report.ok, report.errors
        assert 'version = "1.3.0"' in component.manifest.read_text(encoding="utf-8")
        versions = [r["version"] for r in json.loads(component.output.read_text(encoding="utf-8"))["releases"]]
        assert versions == ["1.3.0", "1.2.3"]

    @pytest.mark.parametrize(
        ("fields", "expected"),
        [
            ({"kind": "fixed"}, "1.2.4"),
            ({"kind": "added"}, "1.3.0"),
            ({"kind": "fixed", "breaking": "true"}, "2.0.0"),
        ],
    )
    def should_derive_the_bump_from_the_entries(self, component, fields, expected):
        write_fragment(component.fragments_dir / "a.md", **fields)
        assert tool.release(component, bump_how="auto").ok
        assert component.version == expected

    def should_let_an_explicit_version_win(self, component):
        write_fragment(component.fragments_dir / "a.md")
        assert tool.release(component, version="1.2.3rc1").ok
        assert json.loads(component.output.read_text(encoding="utf-8"))["releases"][0]["version"] == "1.2.3rc1"

    def should_release_nothing_but_still_consume_internal_fragments(self, component):
        write_fragment(component.fragments_dir / "a.md", kind="internal", title="Pinned scrapli")

        report = tool.release(component)

        assert report.ok
        assert json.loads(component.output.read_text(encoding="utf-8"))["releases"] == []
        assert list(component.fragments_dir.glob("*.md")) == []

    def should_retire_the_planned_item_a_change_completes(self, component):
        write_coming(component.coming_dir / "junos-ztp.md")
        write_coming(component.coming_dir / "other.md", title="Other")
        write_fragment(component.fragments_dir / "a.md", completes="junos-ztp")

        report = tool.release(component)

        assert report.ok
        assert [item["id"] for item in json.loads(component.output.read_text(encoding="utf-8"))["coming"]] == ["other"]
        assert not (component.coming_dir / "junos-ztp.md").exists()

    def should_refuse_an_empty_release(self, component):
        assert "nothing to release" in tool.release(component).errors[0]


class TestBuild:
    def should_refresh_planned_work_and_keep_released_entries(self, component):
        write_fragment(component.fragments_dir / "a.md")
        tool.release(component)
        write_coming(component.coming_dir / "junos-ztp.md", status="in_progress", planned_version="1.4.0")

        report = tool.build([component])

        assert report.ok and report.notes
        data = json.loads(component.output.read_text(encoding="utf-8"))
        assert [r["version"] for r in data["releases"]] == ["1.2.3"]
        assert data["coming"] == [
            {
                "id": "junos-ztp",
                "title": "Junos ZTP",
                "description": "Planned.",
                "status": "in_progress",
                "planned_version": "1.4.0",
                "planned_date": None,
                "refs": [],
            }
        ]

    def should_carry_pending_fragments_as_unreleased_for_development_builds(self, component):
        write_fragment(component.fragments_dir / "a.md")
        tool.release(component)
        write_fragment(component.fragments_dir / "b.md", title="Not out yet")

        assert tool.build([component], include_unreleased=True).ok
        releases = json.loads(component.output.read_text(encoding="utf-8"))["releases"]
        assert [(r["version"], r["date"]) for r in releases] == [(None, None), ("1.2.3", date.today().isoformat())]
        assert releases[0]["entries"][0]["title"] == "Not out yet"
        assert list(component.fragments_dir.glob("*.md")) != []  # a build consumes nothing

        tool.build([component])  # a plain build drops the unreleased block again
        assert [r["version"] for r in json.loads(component.output.read_text(encoding="utf-8"))["releases"]] == ["1.2.3"]

    def should_tell_when_the_compiled_file_is_out_of_date(self, component):
        assert tool.build([component]).ok
        assert tool.build([component], check=True).ok
        write_coming(component.coming_dir / "junos-ztp.md")
        assert "out of date" in tool.build([component], check=True).errors[0]

    def should_refuse_a_compiled_file_of_another_component(self, component):
        component.output.parent.mkdir(parents=True, exist_ok=True)
        component.output.write_text('{"component": "acex", "releases": []}', encoding="utf-8")
        assert "belongs to 'acex'" in tool.build([component]).errors[0]


class TestCheck:
    CODE = "drivers/example/src/acex_driver_example/driver.py"

    def check(self, repo, component, changed, **kwargs):
        return tool.check([component], changed, repo, **kwargs)

    def should_want_a_fragment_when_a_component_changed(self, repo, component):
        report = self.check(repo, component, [("M", self.CODE)])
        assert "acex-driver-example: changed without a changelog entry" in report.errors[0]
        assert "new acex-driver-example --kind" in report.errors[0]

    def should_be_satisfied_by_a_new_fragment(self, repo, component):
        write_fragment(component.fragments_dir / "a.md")
        changed = [("M", self.CODE), ("A", "drivers/example/changelog.d/a.md")]
        assert self.check(repo, component, changed).ok

    def should_not_take_the_readme_of_the_directory_for_a_fragment(self, repo, component):
        changed = [("M", self.CODE), ("A", "drivers/example/changelog.d/README.md")]
        assert not self.check(repo, component, changed).ok

    def should_accept_an_internal_fragment(self, repo, component):
        write_fragment(component.fragments_dir / "a.md", kind="internal", title="Pinned scrapli")
        assert self.check(repo, component, [("M", self.CODE), ("A", "drivers/example/changelog.d/a.md")]).ok

    def should_not_want_one_for_tests_docs_or_planned_work(self, repo, component):
        changed = [
            ("M", "drivers/example/tests/test_driver.py"),
            ("M", "drivers/example/README.md"),
            ("A", "drivers/example/changelog.d/coming/junos-ztp.md"),
            ("M", "docs/guides/drivers.md"),
        ]
        assert self.check(repo, component, changed).ok

    def should_not_count_a_fragment_that_was_only_edited(self, repo, component):
        write_fragment(component.fragments_dir / "a.md")
        assert not self.check(repo, component, [("M", self.CODE), ("M", "drivers/example/changelog.d/a.md")]).ok

    def should_report_a_broken_fragment(self, repo, component):
        (component.fragments_dir / "bad.md").write_text("no front matter", encoding="utf-8")
        assert "front matter" in self.check(repo, component, []).errors[0]

    ON_MAIN = {"acex-driver-example": "1.2.3"}

    def should_want_pending_fragments_released_before_a_new_version_ships(self, repo, component):
        write_fragment(component.fragments_dir / "a.md")
        tool.set_version(component, "1.3.0")

        report = self.check(repo, component, [], release_ready=True, base_versions=self.ON_MAIN)

        assert "1.3.0 is about to be published" in report.errors[0]
        assert tool.release(component).ok
        assert self.check(repo, component, [], release_ready=True, base_versions=self.ON_MAIN).ok

    def should_allow_a_bump_without_notes(self, repo, component):
        tool.set_version(component, "1.3.0")
        assert self.check(repo, component, [], release_ready=True, base_versions=self.ON_MAIN).ok

    def should_let_fragments_wait_while_the_version_is_the_published_one(self, repo, component):
        # The pipeline publishes nothing when the version is unchanged, so
        # nothing ships without its notes; they go out with the next bump.
        write_fragment(component.fragments_dir / "a.md")
        assert self.check(repo, component, [], release_ready=True, base_versions=self.ON_MAIN).ok

    def should_treat_a_component_the_target_branch_lacks_as_new(self, repo, component):
        write_fragment(component.fragments_dir / "a.md")
        assert not self.check(repo, component, [], release_ready=True, base_versions={}).ok


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


class TestGitChanges:
    def should_see_what_a_branch_adds_since_its_merge_base(self, repo, component):
        git(repo, "init", "-q", "-b", "main")
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", "base")
        git(repo, "checkout", "-q", "-b", "feat/adopt")
        write_fragment(component.fragments_dir / "a.md")
        (repo / "drivers/example/src/acex_driver_example/driver.py").write_text("x = 1\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", "change")
        git(repo, "checkout", "-q", "main")
        (repo / "unrelated.txt").write_text("main moved on\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", "main")
        git(repo, "checkout", "-q", "feat/adopt")

        changed = tool.git_changed(repo, "main")

        assert sorted(changed) == [
            ("A", "drivers/example/changelog.d/a.md"),
            ("A", "drivers/example/src/acex_driver_example/driver.py"),
        ]
        assert tool.check([component], changed, repo).ok

    def should_read_the_versions_the_target_branch_has(self, repo, component):
        git(repo, "init", "-q", "-b", "main")
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", "base")
        tool.set_version(component, "1.3.0")

        assert tool.git_versions_at(repo, "main", [component]) == {"acex-driver-example": "1.2.3"}
        assert (
            tool.git_versions_at(repo, "main", [tool.Component("new", "new", repo / "new", "0.1.0", repo / "x")]) == {}
        )

    def should_explain_a_base_that_does_not_exist(self, repo):
        git(repo, "init", "-q")
        with pytest.raises(tool.FragmentError, match="git diff against 'nope' failed"):
            tool.git_changed(repo, "nope")


class TestCommandLine:
    def should_list_validate_build_and_release(self, repo, component, capsys):
        assert tool.main(["new", "example", "--kind", "added", "--title", "Devices can be adopted"], repo=repo) == 0
        assert tool.main(["list"], repo=repo) == 0
        assert "acex-driver-example 1.2.3 (drivers/example): 1 pending" in capsys.readouterr().out
        assert tool.main(["validate"], repo=repo) == 0
        assert tool.main(["build", "--check"], repo=repo) == 1  # coming list not compiled yet
        assert tool.main(["build"], repo=repo) == 0
        assert tool.main(["release", "acex-driver-example", "--bump", "patch", "--date", "2026-10-20"], repo=repo) == 0
        data = json.loads(component.output.read_text(encoding="utf-8"))
        assert (data["releases"][0]["version"], data["releases"][0]["date"]) == ("1.2.4", "2026-10-20")

    def should_take_the_summary_from_the_command_line(self, repo, component):
        tool.main(["new", "example", "--kind", "added", "--title", "Devices can be adopted"], repo=repo)
        args = ["release", "example", "--bump", "minor", "--date", "2026-10-20", "--summary", "Adoption arrives."]
        assert tool.main(args, repo=repo) == 0
        assert json.loads(component.output.read_text(encoding="utf-8"))["releases"][0]["summary"] == "Adoption arrives."

    def should_report_a_compiled_summary_that_has_grown_too_long(self, repo, component, capsys):
        write_fragment(component.fragments_dir / "a.md")
        assert tool.release(component).ok
        data = json.loads(component.output.read_text(encoding="utf-8"))
        data["releases"][0]["summary"] = "y" * 250
        component.output.write_text(json.dumps(data), encoding="utf-8")

        assert tool.main(["validate"], repo=repo) == 1
        assert "keep it under 200" in capsys.readouterr().err

    def should_fail_loudly_on_a_bad_fragment(self, repo, component, capsys):
        (component.fragments_dir / "bad.md").write_text("---\nkind: added\n---\n", encoding="utf-8")
        assert tool.main(["validate"], repo=repo) == 1
        assert "'title' is required" in capsys.readouterr().err

    def should_name_an_unknown_component(self, repo, capsys):
        assert tool.main(["release", "nope"], repo=repo) == 1
        assert "No component 'nope'" in capsys.readouterr().err


PACKAGE_JSON = """{
  "name": "example-ui",
  "private": true,
  "version": "0.4.2",
  "acex": {
    "changelog": {
      "name": "Example web interface",
      "output": "src/changelog.json",
      "paths": ["src", "public", "index.html"]
    }
  }
}
"""

PACKAGE_LOCK = """{
  "name": "example-ui",
  "version": "0.4.2",
  "lockfileVersion": 3,
  "packages": {
    "": {
      "name": "example-ui",
      "version": "0.4.2"
    },
    "node_modules/left-pad": {
      "version": "0.4.2"
    }
  }
}
"""


@pytest.fixture
def web(tmp_path):
    (tmp_path / "changelog.d").mkdir()
    (tmp_path / "package.json").write_text(PACKAGE_JSON, encoding="utf-8")
    (tmp_path / "package-lock.json").write_text(PACKAGE_LOCK, encoding="utf-8")
    # Installed dependencies are never scanned for components.
    (tmp_path / "node_modules" / "dep" / "changelog.d").mkdir(parents=True)
    (tmp_path / "node_modules" / "dep" / "package.json").write_text(PACKAGE_JSON, encoding="utf-8")
    [component] = tool.discover(tmp_path)
    return tmp_path, component


class TestJavaScriptComponent:
    def should_be_found_by_its_fragment_directory_beside_package_json(self, web):
        repo, component = web
        assert (component.id, component.name, component.version) == ("example-ui", "Example web interface", "0.4.2")
        assert component.output == repo / "src" / "changelog.json"
        assert component.manifest == repo / "package.json"

    def should_name_itself_after_the_project_without_options(self, web):
        repo, _ = web
        (repo / "package.json").write_text('{"name": "example-ui", "version": "1.0.0"}', encoding="utf-8")
        [component] = tool.discover(repo)
        assert (component.name, component.output) == ("example-ui", repo / "changelog.json")

    def should_refuse_a_package_json_without_a_version(self, web):
        repo, _ = web
        (repo / "package.json").write_text('{"name": "example-ui"}', encoding="utf-8")
        with pytest.raises(tool.FragmentError, match="needs a name and a version"):
            tool.discover(repo)

    def should_release_into_the_file_the_project_names(self, web):
        _, component = web
        write_fragment(component.fragments_dir / "a.md", kind="added", title="Sites can be filtered by region")

        report = tool.release(component, on=date(2026, 10, 20))

        assert report.ok, report.errors
        data = json.loads(component.output.read_text(encoding="utf-8"))
        assert data["component"] == "example-ui"
        assert (data["releases"][0]["version"], data["releases"][0]["date"]) == ("0.4.2", "2026-10-20")

    def should_bump_package_json_and_keep_the_lock_file_in_step(self, web):
        repo, component = web
        write_fragment(component.fragments_dir / "a.md", kind="fixed", title="The table keeps its sort order")

        report = tool.release(component, bump_how="patch")

        assert report.ok, report.errors
        assert '"version": "0.4.3"' in (repo / "package.json").read_text(encoding="utf-8")
        lock = (repo / "package-lock.json").read_text(encoding="utf-8")
        assert lock.count('"version": "0.4.3"') == 2
        # A dependency that happens to have the same version is not the project's.
        assert lock.count('"version": "0.4.2"') == 1
        assert json.loads(lock)["packages"]["node_modules/left-pad"]["version"] == "0.4.2"

    def should_want_an_entry_only_for_the_paths_it_lists(self, web):
        repo, component = web
        for path in ("src/pages/NodesPage.jsx", "public/logo.svg", "index.html"):
            report = tool.check([component], [("M", path)], repo)
            assert "example-ui: changed without a changelog entry" in report.errors[0], path
        for path in ("package.json", "package-lock.json", ".github/workflows/ci.yml", "eslint.config.js", "README.md"):
            assert tool.check([component], [("M", path)], repo).ok, path

    def should_accept_a_new_fragment_for_a_listed_path(self, web):
        repo, component = web
        write_fragment(component.fragments_dir / "a.md")
        assert tool.check([component], [("M", "src/App.jsx"), ("A", "changelog.d/a.md")], repo).ok

    def should_read_the_version_the_target_branch_has(self, web):
        repo, component = web
        git(repo, "init", "-q", "-b", "main")
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", "base")
        tool.set_version(component, "0.5.0")

        assert tool.git_versions_at(repo, "main", [component]) == {"example-ui": "0.4.2"}

    def should_run_from_the_command_line(self, web, capsys):
        repo, component = web
        assert tool.main(["new", "example-ui", "--kind", "added", "--title", "Sites can be filtered"], repo=repo) == 0
        assert tool.main(["list"], repo=repo) == 0
        assert "example-ui 0.4.2 (.): 1 pending" in capsys.readouterr().out
        assert tool.main(["release", "example-ui", "--bump", "minor", "--date", "2026-10-20"], repo=repo) == 0
        data = json.loads(component.output.read_text(encoding="utf-8"))
        assert data["releases"][0]["version"] == "0.5.0"
