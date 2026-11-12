<!--
The product's highlights: what Settings > What's new shows first.

Written together when a release is cut, one entry per feature that people who use or run ACEX
would recognise, in their words ("ZTP for Cisco switches"). Newest first. The format:

    ## 2026-10-15 ZTP for Cisco switches

    One or two sentences, at most 400 characters. No versions, package names or ticket numbers.

`python scripts/changelog.py brief` collects what changed since the newest entry, for whoever
writes the draft, a person or an assistant. `python scripts/changelog.py validate` checks this file.
Nothing is compiled: an edit that is merged is live in the next image.
-->

## 2026-11-12 Compliance for the whole installation

ACEX measures every node's configuration against what it should have, and every asset's software against the versions you approve. The new Compliance section ranks the best and the worst sites and lists every region, the dashboard shows both figures, and a site's Compliance tab breaks them down per node and per asset.

## 2026-11-12 Approve software versions per vendor or hardware model

Administrators approve the software versions a vendor or hardware model may run and mark one as golden for each operating system, the version to aim for. A model's own versions beat its vendor's, and a device running anything else is reported as not allowed. Settings > Hardware Models chooses which models can be named.

## 2026-11-12 Search the whole inventory from the dashboard

Type in the search field on the dashboard to find nodes, logical nodes, sites, regions, assets, asset clusters and contacts. A node is also found by its management IP address or by the serial number of its asset. Choosing a hit opens it.

## 2026-11-12 ConfigMaps can be loaded from a git repository

Add a git repository under Settings > Git Repositories and ACEX loads the ConfigMaps in it, checks the branch every 30 minutes and loads new commits. A commit with a file that fails to import is not loaded, and the repository shows which file failed.

## 2026-11-12 VLANs and VTP settings are collected from Cisco switches

When ACEX reads a Cisco switch's configuration it now also reads the VTP settings and the VLANs, so they are part of what is compared with the desired configuration.

## 2026-11-09 Run commands and pings on many nodes at once

Choose a list of nodes, run a command or a ping on all of them and read each node's answer as it comes in. Steps can be chained into a workflow, where each step runs on its own nodes and later steps use what earlier ones found.

## 2026-11-09 Apply the configuration of many nodes from a reviewed plan

Pick a part of the configuration, such as the NTP servers. ACEX reads each node live and shows the exact lines that would change, and you apply the plan to the nodes you choose. 

## 2026-11-09 ZTP, Zero touch provisioning

Onboarding unconfigured using DHCP parameters. Complete safe onboarding workflow based on serial number. Discovered devices are acked manually before they receive any configuration to prevent spoofing attacks. 
ZTP flow applies all desired configuration to new devices. If Assets is not defined before, they will be automatically created.

## 2026-11-09 See compliance and how fresh each node's configuration is

Sites show compliance on the Overview and per node on a Compliance tab, and every node says when its configuration was last collected from the device and when it was last changed.

## 2026-11-09 CVE tracker

Initial functionality of the CVE tracker. Connect with your api key from nist.gov and download CVE:s for selected filter and fetch details. More functionality is on the roadmap.

## 2026-11-09 Release notes and versions are part of the product

Settings > What's new shows the highlights, what is planned and the notes of every release. Settings > About lists the version and build of every component, including each agent.

## 2026-10-15 The backend's settings use ACEX_* names

Every backend setting now has a name of the form ACEX_<SECTION>_<FIELD>. The old names are no longer read, so an installation must rename them before upgrading.

## 2026-10-15 ZTP for Cisco switches

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
