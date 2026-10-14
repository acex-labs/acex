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

    def should_pass_the_summary_of_a_release_through(self, tmp_path):
        own = write(
            tmp_path / "own.json",
            "acex",
            "ACEX backend",
            releases=[
                {**release("6.28.0", "2026-10-20", entry("Choose a driver")), "summary": "ZTP gets a driver choice."},
                release("6.27.0", "2026-10-10", entry("Jobs can be cancelled")),
            ],
        )

        [product] = service(own).changelog().sections

        assert [r.summary for r in product.releases] == ["ZTP gets a driver choice.", None]

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

    def should_compress_the_answer_for_a_client_that_accepts_it(self, api):
        response = api.get("/api/v1/changelog", headers={"Accept-Encoding": "gzip"})

        assert response.headers["content-encoding"] == "gzip"
        assert response.headers["vary"] == "Accept-Encoding"
        assert response.json()["sections"][0]["id"] == "product"  # the client decoded it

    @pytest.mark.parametrize("accept", ["identity", "gzip;q=0", ""])
    def should_not_compress_for_a_client_that_does_not_accept_it(self, api, accept):
        response = api.get("/api/v1/changelog", headers={"Accept-Encoding": accept})

        assert "content-encoding" not in response.headers
        assert response.json()["sections"][0]["id"] == "product"

    def should_answer_304_when_the_client_already_has_this_version(self, api):
        first = api.get("/api/v1/changelog")
        etag = first.headers["etag"]
        assert first.headers["cache-control"] == "private, no-cache"

        again = api.get("/api/v1/changelog", headers={"If-None-Match": etag})

        assert again.status_code == 304
        assert again.content == b""
        assert again.headers["etag"] == etag

    def should_keep_the_same_etag_while_the_notes_are_the_same(self, api):
        # `generated_at` moves on every call and must not make every answer a new version.
        assert api.get("/api/v1/changelog").headers["etag"] == api.get("/api/v1/changelog").headers["etag"]

    def should_send_a_new_etag_and_the_new_notes_when_a_deployment_edits_its_file(self, api, tmp_path):
        stale = api.get("/api/v1/changelog").headers["etag"]
        write(
            tmp_path / "extra" / "later.json",
            "later",
            "Later",
            section={"id": "later", "name": "Later"},
            releases=[release("1", "2026-10-19", entry("A newer note"))],
        )

        response = api.get("/api/v1/changelog", headers={"If-None-Match": stale})

        assert response.status_code == 200
        assert response.headers["etag"] != stale
        assert [s["id"] for s in response.json()["sections"]] == ["product", "later", "example"]  # by name


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


class TestHighlights:
    def should_gather_the_product_highlights_across_components_newest_first(self, own, tmp_path):
        data = json.loads(own.read_text())
        data["highlights"] = [
            {"id": "a", "date": "2026-09-01", "title": "Release notes", "components": []},
            {
                "id": "b",
                "date": "2026-10-09",
                "title": "ZTP for Cisco",
                "components": [{"component": "acex", "version": "6.27.0"}],
            },
        ]
        own.write_text(json.dumps(data), encoding="utf-8")
        bundled = tmp_path / "bundled"
        write(bundled / "worker.json", "acex-worker", "ACEX worker")
        data = json.loads((bundled / "worker.json").read_text())
        data["highlights"] = [{"id": "c", "date": "2026-09-20", "title": "Workers run background jobs"}]
        (bundled / "worker.json").write_text(json.dumps(data), encoding="utf-8")

        response = service(own, bundled_dir=bundled).changelog()

        assert [h.title for h in response.highlights] == [
            "ZTP for Cisco",
            "Workers run background jobs",
            "Release notes",
        ]
        assert response.highlights[0].components[0].version == "6.27.0"

    def should_leave_a_deployments_notes_out_of_the_products_highlights(self, own, tmp_path):
        extra = tmp_path / "extra"
        write(extra / "example.json", "example-config", "Example", section={"id": "example", "name": "Example IT"})
        data = json.loads((extra / "example.json").read_text())
        data["highlights"] = [{"id": "x", "date": "2026-10-01", "title": "Our own milestone"}]
        (extra / "example.json").write_text(json.dumps(data), encoding="utf-8")

        assert service(own, extra_dir=extra).changelog().highlights == []

    def should_have_none_when_nobody_wrote_any(self, own):
        assert service(own).changelog().highlights == []

    def should_keep_the_releases_when_one_highlight_is_malformed(self, tmp_path, caplog):
        path = write(
            tmp_path / "own.json", "acex", "ACEX backend", releases=[release("6.27.0", "2026-10-09", entry("Jobs"))]
        )
        data = json.loads(path.read_text())
        data["highlights"] = [
            {"id": "good", "date": "2026-10-09", "title": "ZTP for Cisco"},
            {"id": "bad", "date": "Oct 2026", "title": "A feature"},
            {"id": "worse", "date": "2026-10-09"},
        ]
        path.write_text(json.dumps(data), encoding="utf-8")

        [product] = service(path).changelog().sections

        assert [r.version for r in product.releases] == ["6.27.0"]
        assert [h.title for h in service(path).changelog().highlights] == ["ZTP for Cisco"]
        assert "highlight skipped" in caplog.text

    def should_make_the_ids_unique_across_components(self, own, tmp_path):
        data = json.loads(own.read_text())
        data["highlights"] = [{"id": "20261009-ztp", "date": "2026-10-09", "title": "ZTP"}]
        own.write_text(json.dumps(data), encoding="utf-8")
        bundled = tmp_path / "bundled"
        write(bundled / "worker.json", "acex-worker", "ACEX worker")
        worker = json.loads((bundled / "worker.json").read_text())
        worker["highlights"] = [{"id": "20261009-ztp", "date": "2026-10-09", "title": "ZTP for the worker"}]
        (bundled / "worker.json").write_text(json.dumps(worker), encoding="utf-8")

        ids = [h.id for h in service(own, bundled_dir=bundled).changelog().highlights]

        assert sorted(ids) == ["acex-worker/20261009-ztp", "acex/20261009-ztp"]

    def should_order_the_same_day_by_title_whatever_the_case(self, own):
        data = json.loads(own.read_text())
        data["highlights"] = [
            {"id": "1", "date": "2026-10-09", "title": "zulu"},
            {"id": "2", "date": "2026-10-09", "title": "Älg"},
            {"id": "3", "date": "2026-10-09", "title": "Beta"},
            {"id": "4", "date": "2026-10-09", "title": "alpha"},
        ]
        own.write_text(json.dumps(data), encoding="utf-8")

        assert [h.title for h in service(own).changelog().highlights] == ["alpha", "Beta", "zulu", "Älg"]
