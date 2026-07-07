---
id: checkout-5xx
title: Checkout 5xx / payment confirmation failures
services: [checkout-service]
tags: [5xx, payments, retry, errors, confirm]
summary: Triage steps for elevated 5xx error rates on checkout-service, especially the payment confirmation endpoint.
---
# Checkout 5xx / payment confirmation failures

## Symptoms
- Elevated HTTP 5xx on `checkout-service`, typically concentrated on
  `/api/checkout/confirm`.
- Customers report failed or hanging payments at the final step.

## First response
1. Confirm blast radius in the checkout dashboard (error rate, affected regions).
2. Check the deploy timeline for `checkout-service` — a deploy immediately before
   the alert is the prime suspect.
3. If a recent deploy correlates, **roll back** to the previous known-good release:
   `deployctl rollback checkout-service --to previous`.

## Common causes
- Payment retry/backoff changes causing thundering-herd retries against the PSP.
- Timeout or connection-pool misconfiguration to the payments gateway.
- Schema drift between checkout and the orders service.

## Mitigation
- Roll back the suspect deploy first; verify error rate recovers within ~5 min.
- If rollback is not possible, enable the `checkout.payments.circuit_breaker`
  feature flag to shed load from the failing path.

## Verification
- 5xx rate back under 1% for 10 consecutive minutes.
- Payment success rate restored to baseline in the payments dashboard.
