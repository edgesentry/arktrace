# Human-in-the-Loop Triage Governance

This document defines the operating model for ranking-to-investigation handoff in Phase A screening.

Scope covered by this document:

- Tier taxonomy and minimum evidence requirements
- Evidence policy and over-claim safeguards
- Analyst/officer decision states and handoff lifecycle
- KPI specification for model quality and operations utility

## Decision Responsibility Model

The model ranks candidates. Humans decide actions.

1. Model responsibility:
- Produce ranked candidates with explainable signals.
- Surface uncertainty and confidence boundaries.

2. Human responsibility:
- Assign a review tier based on available evidence.
- Decide escalation to physical investigation.
- Record rationale and evidence references.

3. Governance rule:
- Never treat model score alone as legal or operational proof.
- Every non-cleared decision requires explicit evidence references.

## Tier Taxonomy

Allowed review tiers:

- Confirmed
- Probable
- Suspect
- Cleared
- Inconclusive

### Tier definitions and minimum evidence

1. Confirmed
- Meaning: high-confidence determination with corroborated evidence.
- Minimum evidence: at least 2 independent high-credibility sources OR 1 official designation source with vessel identifier match (MMSI/IMO).

2. Probable
- Meaning: strong signals and corroboration, but not enough for confirmed status.
- Minimum evidence: at least 1 high-credibility source plus consistent model/graph behavior signals.

3. Suspect
- Meaning: early warning; potentially risky pattern with incomplete corroboration.
- Minimum evidence: model-based anomaly pattern plus at least 1 weak/medium external indication.

4. Cleared
- Meaning: reviewed and not recommended for current escalation.
- Minimum evidence: analyst rationale documenting why evidence is insufficient or contradictory.

5. Inconclusive
- Meaning: insufficient data quality or unresolved conflict among signals.
- Minimum evidence: explicit data gap reason (missing identifiers, stale data, conflicting sources).

## Evidence Policy

### Source credibility classes

- High: official sanctions/designation lists, government enforcement notices.
- Medium: reputable investigative reports with dated vessel identifiers.
- Weak: indirect references, partial identifiers, unverified reports.

### Evidence recording requirements

For every reviewed vessel decision, record:

- decision_tier
- decision_timestamp_utc
- reviewer_id
- rationale text (why this tier)
- evidence references (source, URL, publication date)
- identifier basis (MMSI/IMO/name match confidence)

### Over-claim safeguards

- Do not assign Confirmed from a single weak/medium source.
- Do not infer negative truth from absence of public evidence.
- Keep label confidence explicit (high/medium/weak/unknown).
- Re-review stale evidence on a fixed cadence.

## Escalation and Handoff Lifecycle

Decision states:

- queued_review
- in_review
- handoff_recommended
- handoff_accepted
- handoff_completed
- closed

Recommended transition path:

1. queued_review -> in_review
2. in_review -> (confirmed|probable|suspect|cleared|inconclusive)
3. if confirmed/probable and operationally relevant: -> handoff_recommended
4. handoff_recommended -> handoff_accepted (officer)
5. handoff_accepted -> handoff_completed (field outcome attached)
6. -> closed

Transition constraints:

- handoff_recommended requires non-empty rationale + at least one evidence reference.
- handoff_completed requires outcome note and officer attribution.

## KPI Specification

KPI objectives:

- Maintain high triage utility at fixed analyst review capacity.
- Reduce wasted investigations while preserving recall on credible positives.

### Model quality KPIs

- Precision@K: K in {25, 50, 100}
- Recall@K: K in {100, 200}
- AUROC
- PR-AUC
- Calibration error (ECE)

### Operations KPIs

- Hit-rate at top-N review queue
- Escalation acceptance rate (handoff_recommended -> handoff_accepted)
- Wasted investigation rate (handoff_completed with cleared outcome)
- Median review turnaround time

### Tier-aware KPIs

- Tier distribution by region and vessel type
- Tier-specific FP/FN pattern summary from backtesting + reviewed outcomes
- Drift alerts when tier mix or hit-rate deviates from agreed bounds

## Reporting Cadence

- Daily: operational dashboard snapshot (top-N, hit-rate, queue health)
- Weekly: threshold recommendation refresh by region/review capacity
- Monthly: tier-quality and drift review with mitigation actions

## Traceability

Related tracking issues:

- #54 Parent workflow issue
- #55 Taxonomy/evidence/KPI definition
- #56 Schema and API persistence for review decisions
- #57 Dashboard workflow and handoff actions
- #58 Periodic evaluation and threshold tuning loop
