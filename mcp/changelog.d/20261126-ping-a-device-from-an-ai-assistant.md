---
kind: added
title: Ping a device from an AI assistant
---
The MCP server has a tool for each standard action, starting with `ping`.
An assistant, including the ACE-X AI chat, can now check from a device
whether a target is reachable and how fast it answers. Ask, for example,
"can sto-office1-core-1 reach 10.10.0.2?".

The tool runs the action live on the device, as you, and waits for the
answer. A run that takes longer than the action allows goes on by itself, and
the assistant reads it later with `get_action_run`. Every run shows under
Operations › Standard Actions like one you ordered there. Actions only
troubleshoot or collect data; none of them change a device's configuration.
