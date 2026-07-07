---
id: database-incident
title: Database connection / saturation incidents
services: [checkout-service, orders-service, media-service]
tags: [database, db, connections, pool, saturation, deadlock, timeout]
summary: Handling database connection exhaustion, saturation, and deadlocks.
---
# Database connection / saturation incidents

## Symptoms
- Errors mentioning connection pool exhaustion, `too many connections`, or
  query timeouts across one or more services.
- Rising DB CPU, replication lag, or lock waits.

## First response
1. Check DB dashboards: active connections vs. max, CPU, replication lag.
2. Identify the top offending queries (slow query log / performance insights).
3. Correlate with recent deploys that changed queries, ORM usage, or pool size.

## Common causes
- A deploy that raised per-instance pool size beyond the DB's max connections.
- A long-running migration holding locks.
- A missing index turning a frequent query into a table scan.

## Mitigation
- Roll back the suspect deploy or revert the pool-size change.
- Kill long-running/blocking queries if safe.
- Fail over to a replica only as a last resort and per the DBA runbook.

## Verification
- Connection count back under threshold; error rate and latency recovered.
