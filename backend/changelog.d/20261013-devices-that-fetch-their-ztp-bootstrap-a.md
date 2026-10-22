---
kind: added
title: Devices that fetch their ZTP bootstrap are discovered automatically
refs: #314, #312, #318
---
When a new device downloads its ZTP script, the backend queues a discovery: a worker logs in and reports the device's serial number, vendor, model and OS version, starting with Cisco IOS XE. `GET /api/v1/ztp_calls` shows which devices called in and how discovery went; `POST /api/v1/ztp_calls/{source_ip}/retry` runs it again. Needs a RabbitMQ broker and a worker.
