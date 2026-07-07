---
id: service-latency
title: Elevated latency / p99 spikes
services: [media-service, checkout-service, web-frontend]
tags: [latency, p99, slow, performance, timeout]
summary: General playbook for p95/p99 latency spikes across services.
---
# Elevated latency / p99 spikes

## Symptoms
- p95/p99 latency above SLO for a sustained period.
- Requests slow but not necessarily failing (distinct from a 5xx incident).

## First response
1. Identify the slow endpoint(s) and whether latency is CPU-, IO-, or
   dependency-bound in traces.
2. Check for a recent deploy that changed hot-path code or dependencies.
3. Check downstream dependencies (DB, cache, third-party APIs) for saturation.

## Common causes
- N+1 queries or a missing index introduced by a recent change.
- Cache miss storms after a cache flush or key-format change.
- Upstream dependency degradation propagating latency.

## Mitigation
- Roll back the suspect deploy if code/deps changed on the hot path.
- Scale out the affected service if the bottleneck is CPU/throughput.
- Add or restore caching for the hot query.

## Verification
- p99 back within SLO for 15 consecutive minutes.
