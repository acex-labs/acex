# Repeatable image builds

Two builds of the same commit should give the same image, so that what was tried on stage is what reaches production. The images therefore pin what they are built from:

| What | Where it is pinned | How it is refreshed |
|---|---|---|
| The Python base image | the `FROM python:3.13-slim@sha256:…` line of every Dockerfile | Dependabot opens a pull request against `dev` |
| The packages of the backend and the worker | `backend/constraints.txt`, `worker/constraints.txt` | `scripts/lock-images.sh` |
| The packages of the agents and the MCP server | `poetry.lock` in `agents/collection-agent`, `agents/telemetry-agent`, `agents/grafana-sync` and `mcp` | `poetry lock` in the directory |

## The base image

A tag such as `python:3.13-slim` moves; the digest after `@sha256:` does not. A new Python patch release therefore reaches the images as a pull request that can be reviewed and built, and not as a silent change between two builds.

Dependabot (`.github/dependabot.yml`) proposes the new digests, weekly and in one pull request for all images. It reads its configuration from the default branch, so it starts once the file has reached `main`. Until then, or to move earlier, take the digest of the multi-platform image from `docker buildx imagetools inspect python:3.13-slim` and replace it in every Dockerfile.

## The backend and the worker

Their Dockerfiles install with `pip install -c /deps/constraints.txt`. The constraints file lists the exact version of every third-party package the image contains, and pip may install only those versions. The project's own `acex*` packages come from the repository and are not in it.

```bash
scripts/lock-images.sh backend   # or worker, or all
```

The script needs bash and Docker. It builds the real Dockerfile for `linux/amd64` without cache and with an empty constraints file, so pip resolves what the `pyproject.toml` files allow today, reads the result back with `pip freeze` and writes it to the constraints file. Every run therefore upgrades all third-party packages: read `git diff`, run the tests and commit. Allow a few minutes.

Two consequences:

- A dependency that is added to a `pyproject.toml` is installed unpinned until the next refresh, because a constraints file limits versions and does not add packages.
- A requirement that conflicts with a pin, such as a raised lower bound, fails the image build until the pins have been refreshed.

## The agents and the MCP server

Their Dockerfiles run `poetry install --only main` against the committed `poetry.lock`, so a build installs exactly the locked versions and the test packages are not in the image. Client and devkit are path dependencies; the Dockerfiles copy them to `/client` and `/devkit`, where the paths in the agent's `pyproject.toml` resolve as written.

```bash
cd agents/collection-agent && poetry lock
```

The three agents declare the same dependencies and have identical lock files, so lock them together. After a change to a `pyproject.toml` the lock file has to be made again, otherwise `poetry install` stops and says the lock file is out of date. `.gitignore` lists `poetry.lock`; the lock files are tracked all the same, and a new one is added with `git add -f`.

## What is not pinned

- The dependencies of the drivers. Agents and workers install the driver wheels from the backend when they start, and the dependencies are resolved then, so that a driver can change without a new agent image.
- The system packages that the backend image installs with `apt`, and the build requirement `poetry-core` that pip resolves while it builds the project's own packages.

## Checking a change

`.github/workflows/image-build-check.yml` builds, for `linux/amd64` and without publishing, every image whose Dockerfile, constraints file, lock file or `pyproject.toml` a pull request changes, so that a pin that no longer installs fails on the pull request and not after the merge. A change to the `pyproject.toml` of `client` or `devkit` does not start it, although the images contain those packages: refresh the pins in the same pull request when such a change moves a dependency.
