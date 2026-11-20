---
kind: fixed
title: Older devices that only offer CBC ciphers over SSH can be reached
---
The driver now accepts the CBC ciphers (3DES and AES) that some older devices offer over SSH. Collection and jobs against such a device used to fail with "No matching encryption algorithm found". A device that supports a modern cipher still gets one, since the CBC ciphers are only a fallback.
