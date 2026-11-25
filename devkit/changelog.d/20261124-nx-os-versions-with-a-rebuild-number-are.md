---
kind: changed
audience: developer
title: NX-OS versions with a rebuild number are accepted
---
An NX-OS version such as `7.0(3)I7(9)` is now a valid `cisco_nxos` version, where it was rejected and only `7.0(3)I7` could be stored. The number in the last parentheses is the rebuild of the train and is the `build` component of the normalized version, so `7.0(3)I7` sorts before `7.0(3)I7(9)` and `(9)` before `(10)`. `10.2.5`, `9.3(8)` and `7.0(3)I7` are accepted as before; IOS and IOS-XE do not take the rebuild number. A software policy that names `7.0(3)I7` does not approve `7.0(3)I7(9)`: add the exact version to the policy.
