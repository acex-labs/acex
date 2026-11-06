# Releasing

ACEX is released in pieces. Every package (the backend `acex`, `acex-devkit`, `acex-client`, `acex-cli`, `acex-mcp`, the drivers, the agents and the worker) has its own version, and a release is a change of that version which CI publishes: libraries to PyPI, images to GHCR.

This page describes how a release is made, from a change merged on `dev` to a version in production. How to write the release notes is in [Release notes](guides/changelog.md), and how to branch and open pull requests is in the [Development guide](development.md).

## Three environments

| Environment | Runs | Gets there by | Needs |
|---|---|---|---|
| dev | the latest `dev` | every push to `dev` publishes `:dev` images | nothing |
| stage | release candidates, such as `0.17.0rc1` | sending packages with the Release workflow | a changelog entry for every change, and an approval |
| production | stable versions, such as `0.17.0` | merging `dev` into `main` | the candidates made stable |

The repository publishes versions. Which version an environment runs is decided where that environment is deployed.

`dev` is free: anything can be merged there without a changelog entry, so something can be tried out quickly. The entry is asked for when a package is sent to stage, because stage is where a release candidate is tried before it goes to production.

## Sending packages to stage

1. Open **Actions > Release > Run workflow**. Choose the branch `dev`, the channel `rc` and, in **packages**, the packages to send: ids or directories separated by spaces, for example `acex-collection-agent`. Leave it empty to send everything that is due.
2. **Plan.** The run summary lists every package that will change, its old and new version and why it is included. The plan stops, and names the package and the command that fixes it, when a change has no changelog entry:

    ```bash
    python scripts/changelog.py new acex-collection-agent --kind fixed --title "..."
    ```

    Commit the fragment to `dev` and run the workflow again.
3. **Approval.** The `release` environment waits for a reviewer. Read the plan and approve it if it is right.
4. **Pull request.** The workflow opens a pull request into `dev`, named `chore/release-<date>-<run>`, that gives the packages their `rc` versions. Merge it.
5. **Images.** The merge publishes the images with the candidate version, such as `ghcr.io/acex-labs/acex-collection-agent:0.17.0rc1`. They are never tagged `latest`, and nothing is published to PyPI. The same push tags the commit with each candidate it published, named after the package and the version, such as `acex-collection-agent-0.17.0rc1`. The tag is put on when every job of the push has finished without failing.

The same plan can be read locally without changing anything:

```bash
python scripts/changelog.py plan --channel rc acex-collection-agent
```

### What is sent with a package

A package is not always sent alone, because an image holds whatever its `Dockerfile` copies:

- An image that copies a sent package follows it with a patch version. The agents copy `client` and `devkit`, and the backend copies `devkit` and the drivers.
- Code that a sent image copies is sent with it when it has changes waiting. Sending the backend therefore sends a driver or `devkit` with changes waiting, and they appear in the plan with the note *its code is in the image of ...*. Without that, the image on stage would contain changes that no version and no note describe.
- A package that depends on one whose major version changes gets a patch version.

A package that is not named keeps its fragments on `dev` and is not touched.

## Trying it on stage

Run the candidate images in the stage environment and test them. If something is wrong, fix it on `dev` with a new fragment and send the package again: the next candidate is `rc2`. A candidate does not use up the fragments, so the notes stay unreleased until the stable release.

## Releasing to production

1. Run the Release workflow on `dev` with the channel `stable` and the packages that passed on stage. Each candidate loses its suffix (`0.17.0rc2` becomes `0.17.0`), and its fragments are compiled into the release notes with the version and the date. Approve it and merge the pull request it opens, as above.

    The plan stops when what a package ships has changed since its candidate was tagged, because the release would then not be what was tried. What a package ships is its directory (or the `paths` it lists) and, for an image, everything its `Dockerfile` copies, including the `Dockerfile`, the ignore file of the build and the lock files. The plan names the first ten files and how many more there are. Send a new candidate, or revert them. Release notes, the highlights and the roadmap, version numbers, `README` files and tests are not counted. A package that never was a candidate, such as a hotfix, is not compared, and neither is a candidate that was cut on another branch.

    The plan also stops when a candidate has no tag. CI tags a candidate when the push that published it finishes without a failed job, so a push that had one leaves its candidates untagged, and so do candidates cut before tagging existed. If that push is long past, tag the commit that set the version, which the message names, with `git tag <tag> <commit>` and push the tag, or send a new candidate.
2. Open a pull request from `dev` into `main`. It fails when
    - a version still has an `rc` suffix, since a candidate never reaches `main`,
    - a version that is about to be published still has unreleased fragments,
    - an image keeps the version that `main` already has although a package inside it has a new one, or
    - what a package ships has changed since the tag of its newest candidate, which also catches code that reached `dev` after the stable pull request was merged. A change that is only on `main`, such as a hotfix, is listed too: merge `main` into `dev` first.

    The pull request is not asked for new changelog entries for the packages it publishes: their notes were compiled by the stable release, and every change was asked for its entry on the way into `dev`.
3. Merging it publishes every version that is new on `main`: libraries to PyPI, images to GHCR with their version and `latest`, and tags each stable version on the commit that published it. The stable images are built again from the same sources with the suffix removed, since an image reads its version from its package metadata, so retagging a candidate would still report `rc`.

Production is not per package yet. The merge publishes every version on `dev` that is new, and it fails while any candidate remains, so make all candidates stable first.

## Hotfix

A fix for production does not wait for the rest of `dev`:

1. Branch `hotfix/<description>` from `main`, make the fix and add its fragment.
2. Run the Release workflow on the hotfix branch with the channel `stable`. The plan holds the fixed package and the images that contain it, and every other package keeps its version. After the approval the workflow commits the new versions to the branch.
3. Open a pull request into `main`. Merging it publishes as above.
4. Land the same fix on `dev`.

The pull request check does not compare a hotfix with a candidate of the same version cut on `dev`: that candidate is not part of the history the hotfix is merged into.

Candidates are cut on `dev` only.

## Setting it up

For the maintainers of the repository:

- The environment **release** (Settings > Environments) lists the people who may approve a release.
- The secret **RELEASE_TOKEN** is a token that may push branches and open pull requests. Without it the workflow uses the default token, and the pull requests it opens do not start the other checks.
- A tag ruleset (Settings > Rules > Rulesets) for the tags `*-[0-9]*` that forbids deleting and moving them. The check above trusts that a candidate's tag still is where CI put it.
