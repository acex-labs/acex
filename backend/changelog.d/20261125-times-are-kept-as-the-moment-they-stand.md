---
kind: fixed
audience: admin
title: Times are kept as the moment they stand for, not the server's clock
---
Every time ACEX stores (created, last synced, last collected, job times and so on) was kept as the wall clock of the database server and then shown as UTC, so a server in Europe/Amsterdam showed them one hour ahead of the real time in winter and two in summer. The database columns are now `timestamptz`, and the upgrade reads the existing rows in the zone they were written in, so old rows get the right time too. A migration changes 32 columns in 17 tables on PostgreSQL (SQLite is left as it is); take a database dump before upgrading, as for any release with a migration. After the upgrade nothing depends on the time zone of the database server.
