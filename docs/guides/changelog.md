# Release notes

**Settings > What's new** in the web interface shows what was added, changed
and fixed in each release, and what is planned. It is served by
`GET /api/v1/changelog`. Which versions are running is shown on
**Settings > About**, which is fed by `GET /api/v1/health/about`.

The notes are written by the person who makes the change, in the same pull
request, for the network engineers who use ACEX. They ship inside the
packages, so an installation without internet access sees the same notes.

## Writing an entry

Every package that keeps notes has a `changelog.d/` directory beside its
`pyproject.toml` (the backend's is `backend/changelog.d/`). One change, one
file:

```bash
python scripts/changelog.py new backend --kind added --title "Choose which driver a ZTP method uses"
```

This creates `backend/changelog.d/<date>-choose-which-driver-a-ztp-method-uses.md`.
Open it and add the description:

```markdown
---
kind: added
title: Choose which driver a ZTP method uses
refs: #314
---
Each ZTP method now has a driver setting under ZTP > Methods. Devices that
boot through that method are handled by the chosen driver.
```

| Field | Required | Meaning |
|---|---|---|
| `kind` | yes | `added`, `changed`, `fixed`, `removed`, `deprecated` or `security`. `internal` satisfies the pull request check without being published: for CI, refactoring and tests. |
| `title` | yes | One line, at most 80 characters. What a user can now do, or what behaves differently. |
| body | no | The text after the front matter, in Markdown. Anything the user has to do or should know. |
| `breaking` | no | `true` when users must act. Shown first. |
| `audience` | no | `user` (default), `admin` or `developer`. Developer entries are for integrators and driver authors. |
| `refs` | no | Comma-separated pull request or work item references, each optionally followed by a URL: `#316, ADO-1234 https://dev.azure.com/...`. |

Write for the person at the screen, not for the reviewer:

| Avoid | Write |
|---|---|
| Feat/ztp backend | ZTP: devices can be discovered and provisioned from the web interface |
| Install devkit after poetry to ensure local version wins | *(kind: internal)* |
| Split node status into admin_status and provision_status | A node now shows an admin status and a provisioning status instead of one status |

The tool refuses titles that look like commit subjects or branch names.

## What the pull request check does

The `Changelog` workflow runs on every pull request:

1. Every fragment and compiled file parses, and so do the highlights and the
   roadmap.
2. A component with code changes in the pull request has at least one *new*
   fragment. Changes under `tests/`, to `README.md` and to `changelog.d/`
   itself do not count. Label the pull request `no-changelog` to skip the
   check, or add a `kind: internal` fragment: that leaves a trace in the
   repository.
3. The compiled `changelog.json` files are current (`build --check`): they
   change only when a release is cut.
4. Into `main`: a component whose version differs from `main`'s has no
   unreleased fragments, so the version the pipeline is about to publish
   carries its notes.

Locally:

```bash
python scripts/changelog.py check --base origin/dev
```

## Cutting a release

The pipeline publishes a package when its version changes on `main`. The
release notes are stamped in the same change as the version bump:

```bash
python scripts/changelog.py release backend --bump minor   # or --bump auto, patch, major
```

This bumps `backend/pyproject.toml`, moves the fragments into
`backend/src/acex/changelog.json` under the new version and today's date, and
deletes the fragments. Commit
the result with the release. Without `--bump`, the version already in
`pyproject.toml` is used, and a version that is already in the file is
refused. Nobody types a version into an entry.

`--bump auto` reads the fragments: a breaking entry bumps the major version,
new or changed behaviour the minor one, fixes only the patch one.

### A summary of the release

A release with many entries is hard to scan. Give it one sentence about what
it is about, written by whoever cuts the release:

```bash
python scripts/changelog.py release backend --bump minor \
    --summary "ZTP for Cisco switches: discovery, approval and provisioning from the web interface."
```

The sentence is stored with the release and shown above its entries in
Settings > What's new, and in the overview of a component's releases. It is
for the reader who wants the gist (at most 200 characters), so write what
changed for the people who use ACEX, not how. A release without a summary
is shown as before. The summary of an older release can be added or
corrected by editing the `summary` field of that release in `changelog.json`;
`release` and `build` leave older releases as they are.

## Highlights and the roadmap

Settings > What's new opens on the product's highlights: the features worth
telling an ordinary user about, newest first, each with the date it arrived.
Next to them is the roadmap: what is coming. Both belong to the product as a
whole, not to a package, and each is one plain Markdown file that is read as
it is. Nothing is compiled and no tool is needed to edit them, so they can be
changed in the web editor of the repository.

| | File | Written by | When |
|---|---|---|---|
| Highlights | `backend/src/acex/changelog/content/highlights.md` | the team, together | when a release is cut to `main` |
| Roadmap | `backend/src/acex/changelog/content/roadmap.md` | the person who owns the roadmap | whenever the plan changes |

Editing either file needs no changelog entry, and the edit is live with the
next image. A package outside this repository can still carry `highlights`
and `coming` in its own compiled file; they are shown as before.

### Highlights at a release

Nobody writes highlights per package or per pull request. When a release is
cut, the team writes them once, together, in the release pull request (`dev`
into `main`). The tool collects the material:

```bash
python scripts/changelog.py brief                    # everything since the newest highlight
python scripts/changelog.py brief --since 2026-10-01
```

It prints a brief in Markdown: what a highlight is and how to write one, the
format, what is already published, what is on the roadmap, and every change
since then that matters to users and administrators, with the summary of each
release. Give it to whoever drafts the highlights, a person or an AI
assistant: they read the brief, add the entries to `highlights.md` and run
`python scripts/changelog.py validate`. The draft is
then reviewed like any other change in the release pull request, which is
where the team agrees on what the release will be known for.

```markdown
## 2026-10-05 ZTP for Cisco switches

A new, unconfigured Cisco switch can download its bootstrap from ACEX and be
given its rendered configuration. The web interface has a ZTP section for
following it.
```

- A heading is the day the feature arrived (`YYYY-MM-DD`) and what people
  would call it, at most 80 characters, at the level of "ZTP for Cisco
  switches" and not "ZTP script URL moved". A date more than 31 days ahead is
  refused.
- The text below it is one or two sentences, at most 400 characters, for
  someone who does not know the packages. No versions, package names or ticket
  numbers: the page does not lead from a highlight to a release, and the
  releases are under Details.
- Anything before the first heading, and `<!-- comments -->` anywhere, are
  notes to the next editor and are left out.
- Order in the file does not matter: the page lists the newest first, and the
  same day in title order.
- An entry that cannot be read is reported by `validate` and by the pull
  request check, and skipped with a warning by the backend; it never takes the
  others with it.
- Nothing forces a highlight to be written. A release without one is simply
  not in the highlights, and its details are still under each component.

### The roadmap

One person keeps the roadmap, in this one file. An item is a heading,
optionally a few lines directly below it, and the explanation:

```markdown
## Background jobs on separate workers

Status: in progress
When: Q4 2026

Long-running work such as discovery and provisioning is handed to separate
workers, and Activity > Jobs lists the jobs.
```

- `Status` is `considering` (weighed, not decided), `planned`, `in progress`
  or `preview`; it is `planned` when left out.
- `When` and `Version` are optional and free text (`2026-11`, `Q1 2027`,
  `6.30.0`). `Refs` points at the ticket (`Refs: ADO-1234 https://...`). Who
  asked for something belongs in the tracker, not here: this repository is
  public.
- A line that looks like a field but is not one (`Staus: planned`) is refused
  rather than shown as text.
- Settings > What's new shows the items under *Roadmap*: under way first, then
  preview, planned and considered. The product owner decides what goes here;
  a backlog is not a roadmap.
- When an item ships, delete it and let the next release's highlights say so:
  the brief lists the roadmap so that nothing that shipped is forgotten.

### Choosing what to see

Highlights are not filtered. The Details view, which lists every change by
component, shows a point of view:

| Choice | Shows entries tagged |
|---|---|
| Users | `user` |
| Administrators | `user` and `admin` (an administrator is also a user) |
| Developers | `developer` |
| Everyone | all of them |

It starts on the person's role (Administrators for `naas-admin`, otherwise
Users). A choice the person made before wins and is remembered in the
browser. A component whose notes are all for another point of view is marked
in the list and offers to show them.

## Development images

Images built from `dev` carry the pending fragments as an "unreleased"
release, so a development deployment shows what is coming. The workflow
runs `python scripts/changelog.py build --include-unreleased` before the
image build; nothing is committed.

## Publishing notes from your own package

A driver, or any other package installed in the backend, publishes its notes
by declaring where its compiled changelog lives:

```toml
[tool.poetry.plugins."acex.changelog"]
acex-driver-cisco-ioscli = "acex_driver_cisco_ioscli"

[tool.acex.changelog]
name = "Cisco IOS CLI driver"
```

The entry point's value is the package that contains `changelog.json`; the
backend reads it through `importlib.resources` at startup. The component is
identified by its distribution name, which is unique on any package index,
so two parties can never claim the same id. The display name comes from
`[tool.acex.changelog]`, else from the distribution name.

In your own repository, copy `backend/src/acex/changelog/tool.py` (it needs
nothing but Python) or, with the backend installed, run
`python -m acex.changelog.tool --repo . <command>`. Keep a `changelog.d/`
next to your `pyproject.toml` and cut releases the same way.

## Components that run as their own service

The command line, the MCP server, the worker and the agents are not installed
in the backend, so the backend cannot find them through an entry point. They
keep their notes like any other package (a `changelog.d/` beside the
`pyproject.toml`, compiled into `changelog.json` inside the package), and
`backend/Dockerfile` copies each compiled file into
`acex/changelog_components/` when the image is built. The backend reads that
directory with the others and lists them under the product, with the source
`bundled`. A component that is also installed in the backend wins over its
bundled copy.

A new component of this kind needs one `COPY` line in `backend/Dockerfile`.
The notes of a bundled component describe the repository state the image was
built from, which is the release the product ships.

## A project that is not a Python package

The web interface lives in its own repository and ships its notes inside its
JavaScript bundle. The tool treats a `package.json` with a `changelog.d/` beside
it as a component, the same as a `pyproject.toml`. Options sit under
`acex.changelog` in `package.json`:

```json
{
  "name": "acex-frontend",
  "version": "0.0.35",
  "acex": {
    "changelog": {
      "name": "ACEX web interface",
      "output": "src/changelog.json",
      "paths": ["src", "public", "index.html", "Dockerfile"]
    }
  }
}
```

- `name` is what Settings > What's new shows.
- `output` is the compiled file. It must end up in the bundle; the page
  imports it and adds it to the product section next to the backend's notes.
- `paths` lists what changes call for an entry. Without it every file counts
  except tests, READMEs and lock files, which is wrong for a project whose
  root holds CI and tooling files too. A Python package can set `paths` under
  `[tool.acex.changelog]` for the same reason.

Copy `backend/src/acex/changelog/tool.py` to `scripts/changelog.py` in that
repository and run it from the repository root. `release --bump patch` bumps
`package.json` (and the project's own version in `package-lock.json`, when the
lock file is in step), compiles the fragments under the new version and removes
them.

## Notes that belong to one deployment

Some notes must never be part of the product: a customer's configuration
templates, an integrator's config maps, internal rollout information. They
go in a directory the backend reads at runtime:

```bash
ACEX_CHANGELOG_EXTRA_DIR=/etc/acex/changelog.d
```

Each `*.json` file in it has the same shape as a compiled `changelog.json`,
plus a `section`:

```json
{
  "schema_version": 1,
  "section": {"id": "example", "name": "Notes from Example IT"},
  "component": "example-config",
  "name": "Example network configuration",
  "releases": [
    {"version": "2026.10", "date": "2026-10-18", "entries": [
      {"id": "branch-template-v3", "kind": "changed", "title": "Branch office template v3",
       "description": "New branch offices get the v3 template with the updated VLAN plan."}
    ]}
  ],
  "coming": []
}
```

They are shown as their own section after the product's notes, never mixed
with them, and the `product` section id is refused. Who may write them is
whoever can write that directory: mount it from a ConfigMap, or let your own
pipeline generate it, for example from the work items your tracker marks as
published. The directory is read on every request, so updating a file is
enough.
