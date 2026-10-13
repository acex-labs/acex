"""The changelog endpoint: notes gathered from the backend itself, from installed
packages that publish their own, and from a deployment's own files, which stay in
a section of their own."""

import json
from datetime import UTC, datetime
from importlib.metadata import EntryPoint
from types import SimpleNamespace

import pytest
from acex.api import auth
from acex.api.routers.changelog import create_router
from acex.changelog import ChangelogService
from acex.settings import Settings
from fastapi import FastAPI
from fastapi.testclient import TestClient

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


def entry(title, kind="added", **fields):
    return {"id": title.lower().replace(" ", "-"), "kind": kind, "title": title, **fields}


def release(version, date, *entries):
    return {"version": version, "date": date, "entries": list(entries)}


def write(path, component, name, *, releases=(), coming=(), section=None, text=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": 1,
        "component": component,
        "name": name,
        "releases": list(releases),
        "coming": list(coming),
    }
    if section:
        data["section"] = section
    path.write_text(text if text is not None else json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def own(tmp_path):
    return write(
        tmp_path / "own.json",
        "acex",
        "ACEX backend",
        releases=[
            release(
                "6.28.0", "2026-10-20", entry("Choose a driver per ZTP method"), entry("Faster site view", "fixed")
            ),
            release("6.27.0", "2026-10-10", entry("Jobs can be cancelled")),
        ],
        coming=[{"id": "agent-versions", "title": "Agents report their versions"}],
    )


@pytest.fixture
def package(tmp_path, monkeypatch):
    """An installed package with an `acex.changelog` entry point, the way a driver publishes its notes."""
    root = tmp_path / "site-packages" / "example_driver"
    root.mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    write(
        root / "changelog.json",
        "example-acex-driver",
        "Example driver",
        releases=[release("0.4.0", "2026-10-15", entry("Supports the Example 9000 switch"))],
    )
    monkeypatch.syspath_prepend(str(tmp_path / "site-packages"))
    return EntryPoint(name="example-acex-driver", value="example_driver", group="acex.changelog")


def service(own, entry_points=(), **kwargs):
    return ChangelogService(
        own_file=own,
        entry_points=lambda group: [ep for ep in entry_points if ep.group == group],
        now=lambda: NOW,
        **kwargs,
    )


class TestProductSection:
    def should_serve_the_backends_own_notes(self, own):
        response = service(own).changelog()

        [product] = response.sections
        assert (product.id, product.name) == ("product", "ACEX")
        assert [(c.id, c.name, c.source) for c in product.components] == [("acex", "ACEX backend", "self")]
        assert [(r.component, r.version, str(r.date)) for r in product.releases] == [
            ("acex", "6.28.0", "2026-10-20"),
            ("acex", "6.27.0", "2026-10-10"),
        ]
        assert [e.title for e in product.releases[0].entries] == ["Choose a driver per ZTP method", "Faster site view"]
        assert [c.title for c in product.coming] == ["Agents report their versions"]
        assert response.generated_at == NOW

    def should_add_the_notes_of_an_installed_package_through_its_entry_point(self, own, package):
        [product] = service(own, [package]).changelog().sections

        assert [c.id for c in product.components] == ["acex", "example-acex-driver"]
        assert [(r.component, r.version) for r in product.releases] == [
            ("acex", "6.28.0"),
            ("example-acex-driver", "0.4.0"),
            ("acex", "6.27.0"),
        ]

    def should_put_unreleased_entries_first(self, tmp_path):
        own = write(
            tmp_path / "own.json",
            "acex",
            "ACEX backend",
            releases=[release("6.28.0", "2026-10-20", entry("Old")), release(None, None, entry("Pending"))],
        )
        [product] = service(own).changelog().sections
        assert [r.version for r in product.releases] == [None, "6.28.0"]

    def should_skip_a_package_without_a_changelog_file(self, own, caplog):
        missing = EntryPoint(name="bare", value="json", group="acex.changelog")  # a real package, no file
        [product] = service(own, [missing]).changelog().sections
        assert [c.id for c in product.components] == ["acex"]
        assert "no changelog.json in json" in caplog.text

    def should_skip_a_package_that_cannot_be_imported(self, own, caplog):
        [product] = (
            service(own, [EntryPoint(name="x", value="no_such_pkg", group="acex.changelog")]).changelog().sections
        )
        assert [c.id for c in product.components] == ["acex"]
        assert "no_such_pkg" in caplog.text

    def should_answer_without_any_notes_at_all(self, tmp_path):
        assert service(tmp_path / "missing.json").changelog().sections == []

    def should_keep_the_first_of_two_components_with_the_same_id(self, own, tmp_path, caplog):
        extra = tmp_path / "extra"
        write(extra / "dup.json", "acex", "Impostor", section={"id": "example", "name": "Example"})
        sections = service(own, extra_dir=extra).changelog().sections
        assert [s.id for s in sections] == ["product"]
        assert "found twice" in caplog.text


class TestDeploymentSections:
    def should_keep_a_deployments_notes_apart_from_the_product(self, own, tmp_path):
        extra = tmp_path / "extra"
        write(
            extra / "example.json",
            "example-config",
            "Example network configuration",
            section={"id": "example", "name": "Notes from Example IT"},
            releases=[release("2026.10", "2026-10-18", entry("Branch office template v3", "changed"))],
        )

        product, example = service(own, extra_dir=extra).changelog().sections

        assert product.id == "product" and [c.id for c in product.components] == ["acex"]
        assert (example.id, example.name) == ("example", "Notes from Example IT")
        assert [(c.id, c.source) for c in example.components] == [("example-config", "directory")]
        assert example.releases[0].entries[0].title == "Branch office template v3"

    def should_name_a_section_after_the_file_when_none_is_given(self, own, tmp_path):
        extra = tmp_path / "extra"
        write(extra / "integrator.json", "cfg", "Config maps")
        assert [s.id for s in service(own, extra_dir=extra).changelog().sections] == ["product", "integrator"]

    def should_not_let_a_file_join_the_product_section(self, own, tmp_path, caplog):
        extra = tmp_path / "extra"
        write(extra / "sneaky.json", "sneaky", "Sneaky", section={"id": "product", "name": "ACEX"})
        [product] = service(own, extra_dir=extra).changelog().sections
        assert [c.id for c in product.components] == ["acex"]
        assert "reserved for the product" in caplog.text

    def should_skip_a_broken_file_and_still_answer(self, own, tmp_path, caplog):
        extra = tmp_path / "extra"
        write(extra / "broken.json", "x", "x", text="{not json")
        write(
            extra / "wrong.json",
            "x",
            "x",
            text='{"component": "x", "name": "x", "releases": [{"entries": [{"title": 1}]}]}',
        )
        assert [s.id for s in service(own, extra_dir=extra).changelog().sections] == ["product"]
        assert "broken.json" in caplog.text and "wrong.json" in caplog.text

    def should_read_the_directory_on_every_call(self, own, tmp_path):
        extra = tmp_path / "extra"
        extra.mkdir()
        svc = service(own, extra_dir=extra)
        assert len(svc.changelog().sections) == 1
        write(extra / "later.json", "later", "Later", section={"id": "later", "name": "Later"})
        assert len(svc.changelog().sections) == 2

    def should_cope_with_a_directory_that_is_not_there(self, own, tmp_path, caplog):
        assert len(service(own, extra_dir=tmp_path / "nope").changelog().sections) == 1
        assert "is not a directory" in caplog.text


class TestSettings:
    def should_default_to_no_extra_directory(self, monkeypatch):
        monkeypatch.delenv("ACEX_CHANGELOG_EXTRA_DIR", raising=False)
        assert Settings().changelog.extra_dir is None

    def should_read_it_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("ACEX_CHANGELOG_EXTRA_DIR", "/etc/acex/changelog.d")
        assert Settings().changelog.extra_dir == "/etc/acex/changelog.d"


class TestEndpoints:
    @pytest.fixture
    def api(self, tmp_path):
        extra = tmp_path / "extra"
        write(
            extra / "example.json",
            "example-config",
            "Example configuration",
            section={"id": "example", "name": "Notes from Example IT"},
            releases=[release("2026.10", "2026-10-18", entry("Branch office template v3", "changed"))],
        )
        settings = Settings(dev=True, changelog={"extra_dir": str(extra)})
        app = FastAPI()
        app.include_router(create_router(SimpleNamespace(settings=settings)))
        app.dependency_overrides[auth.get_current_user] = lambda: {"preferred_username": "alice"}
        return TestClient(app)

    def should_serve_the_changelog(self, api):
        response = api.get("/api/v1/changelog")

        assert response.status_code == 200
        body = response.json()
        assert body["schema_version"] == 1
        assert [s["id"] for s in body["sections"]] == ["product", "example"]
        product = body["sections"][0]
        assert product["components"][0] == {"id": "acex", "name": "ACEX backend", "source": "self"}
        assert "releases" in product and "coming" in product
        assert body["sections"][1]["releases"][0]["entries"][0]["title"] == "Branch office template v3"


class TestBundledComponents:
    """Agents, the worker and the command line run as their own services and are not installed in the backend;
    the image build puts their compiled files in a directory the backend reads."""

    @pytest.fixture
    def bundled(self, tmp_path):
        directory = tmp_path / "changelog_components"
        write(
            directory / "acex-worker.json",
            "acex-worker",
            "ACEX worker",
            releases=[release("0.3.0", "2026-10-14", entry("Runs ZTP discovery jobs"))],
        )
        write(
            directory / "acex-cli.json",
            "acex-cli",
            "ACEX CLI",
            releases=[release("4.6.0", "2026-10-12", entry("Lists jobs", "added"))],
        )
        return directory

    def should_list_them_in_the_product_section(self, own, bundled):
        [product] = service(own, bundled_dir=bundled).changelog().sections

        assert [(c.id, c.source) for c in product.components] == [
            ("acex", "self"),
            ("acex-cli", "bundled"),
            ("acex-worker", "bundled"),
        ]
        assert {r.component for r in product.releases} == {"acex", "acex-cli", "acex-worker"}

    def should_prefer_an_installed_package_over_a_bundled_copy(self, own, package, bundled):
        write(bundled / "example.json", "example-acex-driver", "Stale copy", releases=[release("0.1.0", "2026-01-01")])

        [product] = service(own, [package], bundled_dir=bundled).changelog().sections

        by_id = {c.id: c for c in product.components}
        assert (by_id["example-acex-driver"].name, by_id["example-acex-driver"].source) == ("Example driver", "package")

    def should_skip_a_bundled_file_that_cannot_be_read(self, own, bundled, caplog):
        (bundled / "broken.json").write_text("{not json", encoding="utf-8")

        [product] = service(own, bundled_dir=bundled).changelog().sections

        assert {c.id for c in product.components} == {"acex", "acex-cli", "acex-worker"}
        assert "broken.json" in caplog.text

    def should_be_fine_without_the_directory(self, own, tmp_path):
        [product] = service(own, bundled_dir=tmp_path / "missing").changelog().sections
        assert [c.id for c in product.components] == ["acex"]
