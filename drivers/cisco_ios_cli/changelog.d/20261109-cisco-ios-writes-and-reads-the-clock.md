---
kind: fixed
title: Cisco IOS writes and reads the clock timezone
---
The timezone of `system.clock.config`, for example `CET 1`, is written as `clock timezone CET 1` and read from the running configuration. IOS reports the minutes as well (`CET 1 0`); a zero is left out so the device and the declared value compare equal. An offset with real minutes, such as `IST 5 30`, is kept.
