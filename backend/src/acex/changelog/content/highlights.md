<!--
The product's highlights: what Settings > What's new shows first.

Written together when a release is cut, one entry per feature that people who use or run ACEX
would recognise, in their words ("ZTP for Cisco switches"). Newest first. The format:

    ## 2026-10-05 ZTP for Cisco switches

    One or two sentences, at most 400 characters. No versions, package names or ticket numbers.

`python scripts/changelog.py brief` collects what changed since the newest entry, for whoever
writes the draft, a person or an assistant. `python scripts/changelog.py validate` checks this file.
Nothing is compiled: an edit that is merged is live in the next image.
-->

## 2026-10-09 The backend's settings use ACEX_* names

Every backend setting now has a name of the form ACEX_<SECTION>_<FIELD>. The old names are no longer read, so an installation must rename them before upgrading.

## 2026-10-05 ZTP for Cisco switches

A new, unconfigured Cisco switch can download its bootstrap from ACEX and be given its rendered configuration. The web interface has a ZTP section for following it.

## 2026-09-30 Nodes have an admin status and a provisioning status

A node's state is split in two: whether it is meant to be in service (planned, active, decommissioned) and how far provisioning has come. Tables, filters and agent match rules use both.

## 2026-09-25 Monitoring copes with nodes that cannot be rendered

A node that cannot be rendered no longer breaks a telemetry agent's configuration, and the agent's page shows which nodes were covered and which were not.

## 2026-09-15 Supported hardware and operating systems are declared

Assets must use a supported vendor and operating system, and the supported vendors, hardware models and operating systems can be listed.

## 2026-09-10 An MCP server that reads as the signed-in user

AI assistants sign in and read devices, intended and collected configuration, drift and cabling as the signed-in user. The earlier tool set is replaced.

## 2026-09-10 The AI assistant shows its steps and opens pages

The assistant shows the steps it takes and can offer a button that opens the page you asked about. Requests fall back to another provider or model when one fails.

## 2026-09-08 Manage sites, regions, nodes and assets in the web interface

Sites, regions, logical nodes, assets and nodes can be created, edited and deleted from the web interface, with links between a node and its asset and logical node.

## 2026-09-08 Report a bug from any page

Anyone can report a bug from any page, with a severity and steps to reproduce. Reports are delivered to Slack and Azure DevOps when those are configured.

## 2026-08-27 Import nodes, assets, sites and regions from CSV

Nodes, assets and management connections, and sites and regions, can be imported from CSV files.

## 2026-06-11 Port layouts for 119 Cisco hardware models

Interface names for stacked and modular Cisco switches are built per hardware model, with port layouts for 119 models.

## 2026-05-05 Grafana is kept in step with ACEX

An agent creates the datasources and dashboards ACEX generates in a Grafana instance and removes dashboards that were removed from ACEX.

## 2026-05-01 Juniper Junos devices

ACEX renders Junos configuration as set commands and applies it over SSH. Reading a device's configuration back was not yet supported in the first version.
