# Docstribe AI — OPD Clinical Dashboard

A triage tool that takes raw OPD patient JSON and turns it into something a doctor can actually act on in under 30 seconds.

---

## What I Was Going For

Most clinical dashboards show you data. This one tries to show you decisions — specifically, which patient needs something done today and what that something is. The design constraint I gave myself: if an insight can't be traced back to a specific visit note, lab value, or call log entry, it doesn't appear. No hallucinated flags, no vague summaries.

---

## How It Works

The pipeline is two tracks running in parallel — an LLM call and a deterministic engine — and the deterministic one always wins on conflicts.

```
Raw JSON → patient_transformer.py  compact payload per patient
         → Cohere Command R+        extracts risk, cohort, variance, progression
         → normalize_patient_data() fixes whatever the LLM got wrong (types, nulls, bad enums)
         → risk_engine.py           hard overrides on lab/vital thresholds
         → variance_engine.py       10 rule-based variance checks
         → fallback_engine.py       full rebuild from raw data if LLM fails entirely
         → FastAPI + Next.js        cached for 30 min, served to frontend
```

The LLM's job is clinical language and nuance. The deterministic engine's job is to make sure the LLM can't talk a critically abnormal SpO2 down to "medium risk."

---

## Prompt Design

Cohere gets a strict JSON schema — no markdown, no extra keys, schema violations are caught downstream by `normalize_patient_data()`. The important constraints baked into the prompt:

- Every `risk_flag`, `next_action`, and `progression_metric` must include a `source` object with `type`, `description`, and `visit_number`. No source = not shown.
- `progression_status` must compare at least 2 visits. Single-visit trend guesses are explicitly disallowed.
- Fabrication is called out by name in the prompt. It sounds obvious but it helps.

---

## Cohort Buckets

Keyword scoring across `department`, `known_conditions`, and `presenting_complaints`. First match wins. If someone has 2+ major systems in play with no clear winner, they go into Multi-Morbid / Complex — which is often the most important bucket to watch anyway.

Buckets: Poorly Controlled Diabetic · Hypertension Follow-up · Cardiac / Coronary · Orthopedic / Post-Surgical · Complex Neurological · Multi-Morbid / Complex · General Follow-up.

LLM output gets validated after the fact: exact match → fuzzy keyword match → deterministic fallback. The LLM is rarely wrong here but when it is, it tends to be confidently wrong.

---

## Care-Path Variance

10 rules in `variance_engine.py`. A variance fires if any one of them is true — it's OR logic, not AND. The ones that catch the most in this dataset: overdue `due_date` still pending, patient deferring (detected via call transcript keywords), and financial barrier. The HbA1c-without-insulin-escalation rule is the most clinically opinionated one and I'd want a clinician to review it before it goes to production.

---

## Grounding and Validation

The short version: the LLM can raise a risk level, it cannot lower one. `risk_engine.py` applies hard escalations to `high` on: HbA1c ≥ 9.0, Creatinine ≥ 2.0, SpO2 < 94%, WBC > 12,000 + CRP > 20, K < 3.0, Na < 130, or rising NT-proBNP across 2+ visits. These fire regardless of what Cohere decided.

If the LLM call fails or returns a partial response, `fallback_engine.py` rebuilds the entire dashboard deterministically. No patient disappears from the worklist because of an API error.

Risk levels: `high` · `medium` · `low`.

---

## What Doesn't Work Well Yet

The single-batch LLM call is the biggest structural weakness — one malformed patient record can break the entire response. Lab-based rules only fire when labs are actually present in the JSON, so patients with sparse records get less scrutiny than they might deserve. And there's no persistent storage, so a coordinator marking an action as done doesn't survive a page refresh.

The risk logic is also heuristic, not formula-based. It works on these 10 patients but I wouldn't claim it generalises without clinician review. No GRACE scores, no TIMI, no Lee RCRI — those are the right tools and they're not here yet.

---

## What I'd Change With More Time

**1. Send one LLM call per patient, not one call for all 10**
Right now if P-0006's record is malformed, the entire batch response can break. If each patient gets its own call, one bad record fails quietly and the other 9 still work fine.

**2. Use real clinical scores for risk, not just rules**
For P-0001 (stable angina, TMT positive) — a GRACE score would give an actual 6-month mortality estimate based on age, BP, creatinine, and ST changes. Much more trustworthy than "BP is high and labs are worsening = HIGH."

**3. Track how fast things are changing, not just which direction**
Currently the trend for P-0006 is "worsening" because NT-proBNP went 1840 → 2240. But it went up 400 points in 5 months. If it went up 400 points in 3 weeks, that's a completely different situation. The system can't tell the difference right now.

**4. Show the doctor when a rule overrode the LLM**
If Cohere said "medium risk" but `risk_engine.py` bumped it to high because SpO2 was 91%, the clinician should see that — something like `⚠ escalated by SpO2 threshold`. Right now it just shows "high" with no explanation of why.

**5. Give the prompt some examples of good vs bad output**
The prompt currently has no examples — it just describes the rules. Adding 2-3 annotated patient examples (here's a good risk summary, here's what a bad one looks like) would make Cohere's clinical language more consistent and reduce vague outputs like "patient should be monitored."
