"""Changelog fragments: one file per change, written by the author, stamped with the
version when the release is cut. Nobody edits a shared file and nobody types a version."""

import json
import subprocess
from datetime import date, timedelta
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


def write_content(repo: Path, *, highlights: str | None = None, roadmap: str | None = None) -> Path:
    content = repo / tool.CONTENT_PATH
    content.mkdir(parents=True, exist_ok=True)
    if highlights is not None:
        (content / tool.HIGHLIGHTS_FILE).write_text(highlights, encoding="utf-8")
    if roadmap is not None:
        (content / tool.ROADMAP_FILE).write_text(roadmap, encoding="utf-8")
    return content


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

    def should_refuse_an_empty_release(self, component):
        assert "nothing to release" in tool.release(component).errors[0]


class TestBuild:
    def should_keep_the_released_entries(self, component):
        write_fragment(component.fragments_dir / "a.md")
        tool.release(component)

        report = tool.build([component])

        assert report.ok
        data = json.loads(component.output.read_text(encoding="utf-8"))
        assert [r["version"] for r in data["releases"]] == ["1.2.3"]
        assert (data["coming"], data["highlights"]) == ([], [])

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
        component.output.write_text(component.output.read_text(encoding="utf-8").replace("[]", "[ ]"), encoding="utf-8")
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

    def should_not_want_one_for_tests_docs_or_a_file_below_the_fragment_directory(self, repo, component):
        changed = [
            ("M", "drivers/example/tests/test_driver.py"),
            ("M", "drivers/example/README.md"),
            ("A", "drivers/example/changelog.d/notes/idea.md"),
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
        assert tool.main(["build", "--check"], repo=repo) == 1  # the compiled file is not written yet
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


HIGHLIGHTS = """<!-- A note for whoever edits this file: not part of any highlight. -->

## 2026-10-09 The backend's settings use ACEX names

Every setting now starts with ACEX_. The old names are no longer read.

## 2026-10-05 ZTP for Cisco switches

A new, unconfigured switch can fetch its bootstrap from ACEX and be given its configuration.

More than one paragraph is fine,

### and so is a smaller heading inside the text.

## 2026-10-05 Alerts for nodes that stop answering
"""

ROADMAP = """<!-- Kept by one person. -->

## Background jobs on separate workers

Status: in progress
When: Q4 2026

Long-running work is handed to workers through a broker.

## Agents report their versions

Settings > About will show the agents too.

## ZTP for Juniper

Status: considering
Version: 7.0.0
Refs: #321, ADO-1234 https://dev.azure.com/x/_workitems/edit/1234

Only if there is demand.
"""


class TestHighlightsFile:
    def should_be_read_newest_first_without_components(self, tmp_path):
        content = write_content(tmp_path, highlights=HIGHLIGHTS)

        found, problems = tool.read_highlights(content / tool.HIGHLIGHTS_FILE)

        assert problems == []
        assert [(h["id"], h["date"], h["title"]) for h in found] == [
            ("20261009-the-backend-s-settings-use-acex-names", "2026-10-09", "The backend's settings use ACEX names"),
            ("20261005-alerts-for-nodes-that-stop-answering", "2026-10-05", "Alerts for nodes that stop answering"),
            ("20261005-ztp-for-cisco-switches", "2026-10-05", "ZTP for Cisco switches"),
        ]
        assert all(h["components"] == [] for h in found)

    def should_keep_the_text_under_the_heading_and_nothing_else(self, tmp_path):
        content = write_content(tmp_path, highlights=HIGHLIGHTS)

        found, _ = tool.read_highlights(content / tool.HIGHLIGHTS_FILE)

        by_title = {h["title"]: h["description"] for h in found}
        assert by_title["The backend's settings use ACEX names"] == (
            "Every setting now starts with ACEX_. The old names are no longer read."
        )
        assert by_title["ZTP for Cisco switches"].endswith("### and so is a smaller heading inside the text.")
        assert by_title["Alerts for nodes that stop answering"] is None
        assert "note for whoever edits" not in " ".join(filter(None, by_title.values()))

    @pytest.mark.parametrize("separator", ["", " ", " - ", " – ", " — ", ": ", " · "])
    def should_take_the_title_after_the_date_with_or_without_a_separator(self, tmp_path, separator):
        content = write_content(tmp_path, highlights=f"## 2026-10-09{separator}Port layouts\n\nText.\n")

        found, problems = tool.read_highlights(content / tool.HIGHLIGHTS_FILE)

        assert problems == []
        assert [h["title"] for h in found] == ["Port layouts"]

    def should_be_empty_when_there_is_no_file(self, tmp_path):
        assert tool.read_highlights(tmp_path / "missing.md") == ([], [])

    def should_order_the_same_day_by_title_whatever_the_case(self, tmp_path):
        text = "\n".join(f"## 2026-10-09 {title}\n" for title in ("zulu", "Älg", "Beta", "alpha"))
        content = write_content(tmp_path, highlights=text)

        found, _ = tool.read_highlights(content / tool.HIGHLIGHTS_FILE)

        assert [h["title"] for h in found] == ["alpha", "Beta", "zulu", "Älg"]

    @pytest.mark.parametrize(
        "entry, message",
        [
            ("## ZTP for Cisco switches\n\nText.", "must start with the day it arrived"),
            ("## 20261009 ZTP\n\nText.", "must start with the day it arrived"),
            ("## 2026-02-30 ZTP\n\nText.", "is not a date"),
            ("## 2026-10-9 ZTP\n\nText.", "must start with the day it arrived"),
            (f"## 2026-10-09 {'x' * 81}\n\nText.", "keep it under 80"),
            ("## 2026-10-09 feat: choose a driver\n\nText.", "looks like a commit subject"),
            (f"## 2026-10-09 ZTP\n\n{'word ' * 90}", "keep it under 400"),
            (f"## {date.today() + timedelta(days=400)} ZTP\n\nText.", "days ahead"),
        ],
    )
    def should_report_an_entry_that_breaks_the_format_and_keep_the_rest(self, tmp_path, entry, message):
        content = write_content(tmp_path, highlights=f"{entry}\n\n## 2026-10-01 A good one\n\nFine.\n")

        found, problems = tool.read_highlights(content / tool.HIGHLIGHTS_FILE)

        assert [h["title"] for h in found] == ["A good one"]
        [problem] = problems
        assert message in problem and tool.HIGHLIGHTS_FILE in problem

    def should_refuse_the_same_day_and_title_twice(self, tmp_path):
        content = write_content(tmp_path, highlights="## 2026-10-09 ZTP\n\nA.\n\n## 2026-10-09 ZTP\n\nB.\n")

        found, problems = tool.read_highlights(content / tool.HIGHLIGHTS_FILE)

        assert [h["description"] for h in found] == ["A."]
        assert "already a highlight" in problems[0]


class TestRoadmapFile:
    def should_be_read_in_the_order_it_is_written(self, tmp_path):
        content = write_content(tmp_path, roadmap=ROADMAP)

        found, problems = tool.read_roadmap(content / tool.ROADMAP_FILE)

        assert problems == []
        assert [(i["title"], i["status"]) for i in found] == [
            ("Background jobs on separate workers", "in_progress"),
            ("Agents report their versions", "planned"),
            ("ZTP for Juniper", "considering"),
        ]

    def should_read_the_fields_under_the_heading_and_the_text_after_them(self, tmp_path):
        content = write_content(tmp_path, roadmap=ROADMAP)

        jobs, agents, juniper = tool.read_roadmap(content / tool.ROADMAP_FILE)[0]

        assert jobs == {
            "id": "background-jobs-on-separate-workers",
            "title": "Background jobs on separate workers",
            "description": "Long-running work is handed to workers through a broker.",
            "status": "in_progress",
            "planned_version": None,
            "planned_date": "Q4 2026",
            "components": [],
            "refs": [],
        }
        assert agents["description"] == "Settings > About will show the agents too."
        assert (juniper["planned_version"], juniper["planned_date"]) == ("7.0.0", None)
        assert juniper["refs"] == [
            {"label": "#321", "url": None},
            {"label": "ADO-1234", "url": "https://dev.azure.com/x/_workitems/edit/1234"},
        ]

    @pytest.mark.parametrize("word", ["planned", "Planned", "in progress", "In Progress", "in_progress", "preview"])
    def should_take_the_status_the_way_people_write_it(self, tmp_path, word):
        content = write_content(tmp_path, roadmap=f"## Something\n\nStatus: {word}\n\nText.\n")

        [item], problems = tool.read_roadmap(content / tool.ROADMAP_FILE)

        assert problems == []
        assert item["status"] == word.lower().replace(" ", "_")

    def should_be_empty_when_there_is_no_file(self, tmp_path):
        assert tool.read_roadmap(tmp_path / "missing.md") == ([], [])

    def should_read_an_item_that_is_only_a_heading(self, tmp_path):
        content = write_content(tmp_path, roadmap="## A rough idea\n")

        [item], _ = tool.read_roadmap(content / tool.ROADMAP_FILE)

        assert (item["status"], item["description"]) == ("planned", None)

    def should_take_a_text_that_only_looks_like_a_field_for_what_it_is(self, tmp_path):
        content = write_content(tmp_path, roadmap="## Idea\n\nAgents report their version: planned for autumn.\n")

        [item], problems = tool.read_roadmap(content / tool.ROADMAP_FILE)

        assert problems == []
        assert item["description"] == "Agents report their version: planned for autumn."

    @pytest.mark.parametrize(
        "item, message",
        [
            ("## Idea\n\nStatus: soon\n\nText.", "Status must be one of considering, planned, in progress, preview"),
            ("## Idea\n\nStaus: planned\n\nText.", "unknown field 'Staus' (known: Status, When, Version, Refs)"),
            ("## Idea\n\nStatus: planned\nOwner: Johan\n\nText.", "unknown field 'Owner'"),
            (f"## {'x' * 81}\n\nText.", "keep it under 80"),
        ],
    )
    def should_report_an_item_that_breaks_the_format_and_keep_the_rest(self, tmp_path, item, message):
        content = write_content(tmp_path, roadmap=f"{item}\n\n## A good one\n\nFine.\n")

        found, problems = tool.read_roadmap(content / tool.ROADMAP_FILE)

        assert [i["title"] for i in found] == ["A good one"]
        [problem] = problems
        assert message in problem and tool.ROADMAP_FILE in problem

    def should_refuse_the_same_title_twice(self, tmp_path):
        content = write_content(tmp_path, roadmap="## Jobs\n\nA.\n\n## jobs\n\nB.\n")

        found, problems = tool.read_roadmap(content / tool.ROADMAP_FILE)

        assert [i["description"] for i in found] == ["A."]
        assert "already an item" in problems[0]


class TestContentChecks:
    BACKEND = "backend/src/acex/changelog/content"

    @pytest.fixture
    def backend(self, tmp_path):
        root = tmp_path / "backend"
        (root / "src" / "acex").mkdir(parents=True)
        (root / "changelog.d").mkdir()
        (root / "pyproject.toml").write_text(
            '[tool.poetry]\nname = "acex"\nversion = "6.27.0"\npackages = [{ include = "acex", from = "src" }]\n',
            encoding="utf-8",
        )
        [component] = tool.discover(tmp_path)
        return tmp_path, component

    def should_be_checked_by_validate_when_a_directory_is_given(self, tmp_path, component):
        content = write_content(tmp_path, highlights="## Not dated\n", roadmap="## Idea\n\nStatus: soon\n")

        assert len(tool.validate([component], content=content).errors) == 2
        assert tool.validate([component]).ok  # not given: not looked at

    def should_be_checked_by_the_pull_request_check(self, backend):
        repo, component = backend
        write_content(repo, roadmap="## Idea\n\nStatus: soon\n")

        report = tool.check([component], [], repo)

        assert "Status must be one of" in report.errors[0]

    def should_not_call_for_an_entry_when_only_the_highlights_or_the_roadmap_change(self, backend):
        repo, component = backend
        write_content(repo, highlights="## 2026-10-09 ZTP\n\nText.\n", roadmap="## Idea\n")
        changed = [("M", f"{self.BACKEND}/roadmap.md"), ("M", f"{self.BACKEND}/highlights.md")]

        assert tool.check([component], changed, repo).ok

    def should_still_call_for_an_entry_when_the_code_changed_next_to_them(self, backend):
        repo, component = backend
        changed = [("M", f"{self.BACKEND}/roadmap.md"), ("M", "backend/src/acex/api/routers/nodes.py")]

        assert "changed without a changelog entry" in tool.check([component], changed, repo).errors[0]

    def should_not_take_a_file_below_the_fragment_directory_for_a_fragment(self, backend):
        repo, component = backend
        changed = [("M", "backend/src/acex/api/routers/nodes.py"), ("A", "backend/changelog.d/notes/idea.md")]

        assert not tool.check([component], changed, repo).ok

    def should_find_the_repositorys_own_files_valid(self):
        repo = Path(__file__).resolve().parents[2]
        content = repo / tool.CONTENT_PATH

        assert tool.content_problems(content) == []
        assert tool.read_highlights(content / tool.HIGHLIGHTS_FILE)[0], "the repository ships highlights"
        assert tool.read_roadmap(content / tool.ROADMAP_FILE)[0], "the repository ships a roadmap"

    def should_be_where_the_backend_reads_them(self):
        from acex.changelog import service

        assert service.CONTENT_DIR.samefile(Path(__file__).resolve().parents[2] / tool.CONTENT_PATH)


class TestBrief:
    @pytest.fixture
    def released(self, repo, component):
        write_fragment(component.fragments_dir / "a.md", title="Old thing", body="Before the highlight.")
        tool.release(component, version="1.2.3", on=date(2026, 10, 1))
        write_fragment(
            component.fragments_dir / "b.md",
            title="Devices can be adopted",
            body="An unconfigured device is adopted from the web interface. It keeps its settings.",
        )
        write_fragment(component.fragments_dir / "c.md", kind="changed", title="The URL moved", breaking="true")
        write_fragment(component.fragments_dir / "d.md", title="A new Python hook", audience="developer")
        write_fragment(component.fragments_dir / "e.md", kind="internal", title="Ruff format")
        tool.release(component, version="1.3.0", on=date(2026, 10, 10), summary="Adopting devices gets easier.")
        write_fragment(component.fragments_dir / "f.md", kind="fixed", title="Still waiting", body="Not out yet.")
        write_content(
            repo,
            highlights="## 2026-10-05 ZTP for Cisco switches\n\nText.\n\n## 2026-09-01 Older\n\nText.\n",
            roadmap=ROADMAP,
        )
        return repo, component

    def should_collect_what_changed_since_the_newest_highlight(self, released):
        repo, component = released

        text = tool.brief([component], repo / tool.CONTENT_PATH)

        assert text.startswith("# Highlights for the next release")
        assert "## Changes since 2026-10-05" in text
        assert "### acex-driver-example 1.3.0 (2026-10-10)" in text
        assert "_Adopting devices gets easier._" in text
        assert "- [added] Devices can be adopted - An unconfigured device is adopted from the web interface." in text
        assert "- [changed] The URL moved (breaking)" in text
        assert "### acex-driver-example (not released yet)" in text and "- [fixed] Still waiting - Not out yet." in text

    def should_leave_out_what_was_before_the_highlight_and_what_users_cannot_see(self, released):
        repo, component = released

        text = tool.brief([component], repo / tool.CONTENT_PATH)

        assert "Old thing" not in text and "1.2.3" not in text
        assert "A new Python hook" not in text  # a developer's concern
        assert "Ruff format" not in text  # internal, never published

    def should_show_what_is_published_and_what_is_planned(self, released):
        repo, component = released

        text = tool.brief([component], repo / tool.CONTENT_PATH)

        assert "- 2026-10-05 ZTP for Cisco switches\n- 2026-09-01 Older" in text
        assert "- Background jobs on separate workers (in progress)" in text
        assert "- ZTP for Juniper (considering)" in text
        assert "backend/src/acex/changelog/content/highlights.md" in text

    def should_take_the_starting_day_from_the_caller(self, released):
        repo, component = released

        text = tool.brief([component], repo / tool.CONTENT_PATH, since=date(2026, 9, 1))

        assert "## Changes since 2026-09-01" in text and "1.2.3" in text and "Old thing" in text

    def should_cope_with_no_highlights_yet(self, repo, component):
        write_fragment(component.fragments_dir / "a.md", title="First thing")

        text = tool.brief([component], repo / tool.CONTENT_PATH)

        assert "## All changes" in text and "(none yet)" in text and "(empty)" in text
        assert "- [added] First thing" in text

    def should_say_so_when_nothing_changed_for_users(self, repo, component):
        write_content(repo, highlights="## 2026-10-05 ZTP\n\nText.\n")
        write_fragment(component.fragments_dir / "a.md", kind="internal", title="Ruff format")

        assert "Nothing for users or administrators since then." in tool.brief([component], repo / tool.CONTENT_PATH)

    def should_be_printed_by_the_command_line(self, released, capsys):
        repo, _ = released

        assert tool.main(["brief"], repo=repo) == 0
        assert "## Changes since 2026-10-05" in capsys.readouterr().out
        assert tool.main(["brief", "--since", "2026-09-01"], repo=repo) == 0
        assert "## Changes since 2026-09-01" in capsys.readouterr().out

    def should_report_a_bad_day_without_a_traceback(self, released, capsys):
        repo, _ = released

        assert tool.main(["brief", "--since", "yesterday"], repo=repo) == 1
        assert "--since" in capsys.readouterr().err

    def should_have_the_validate_command_look_at_the_two_files(self, repo, capsys):
        write_content(repo, highlights="## Not dated\n")

        assert tool.main(["validate"], repo=repo) == 1
        assert "must start with the day it arrived" in capsys.readouterr().err
