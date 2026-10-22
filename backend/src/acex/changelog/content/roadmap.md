<!--
The roadmap: what is coming, shown under Settings > What's new > Roadmap. One person keeps it.

An item is a heading, optionally a few lines directly below it, and the explanation:

    ## Background jobs on separate workers

    Status: in progress
    When: Q4 2026

    What it means for the people who use ACEX, in a few sentences.

Status is considering, planned, in progress or preview (planned when left out). When, Version and
Refs (tickets, for example #123) are optional. When an item ships, delete it here and add a
highlight. `python scripts/changelog.py validate` checks this file. Nothing is compiled.
-->

## Agents and the worker report their versions

Status: planned

Collection agents, telemetry agents, the Grafana sync agent and the worker
will report their version and the drivers they run to the backend, so that
Settings > About can show them next to the backend and the web interface,
also when they run at another site.

## Background jobs on separate workers

Status: in progress

Long-running work such as discovery and provisioning is handed to separate
workers through RabbitMQ, and the Activity > Jobs page lists the jobs and lets
you requeue or cancel them.

## ZTP discovery, approval and provisioning

Status: in progress

A device that fetches its bootstrap is discovered, what it reports is reviewed
and approved, and its configuration is provisioned. The web interface follows
each node through the stages.
