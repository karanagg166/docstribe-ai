"""Deterministic fallback engine for clinical insights.

Used when Cohere is unavailable or returns an invalid response.
All functions here are pure Python — no LLM calls.
"""

from datetime import datetime
from typing import Any, Dict, List

from app.models.schemas import (
    CarePathVariance,
    CohortBucket,
    ConversionFunnelSummary,
    ConversionStatus,
    DashboardResponse,
    DashboardSummary,
    NextAction,
    PatientInsight,
    PendingActionsSummary,
    ProgressionStatus,
    RiskFlag,
    RiskLevel,
    SourceTrace,
    VisitSummary,
)


# ─── Public entry point ────────────────────────────────────────


def generate_fallback_response(patients: List[Dict[str, Any]]) -> DashboardResponse:
    """Produce a fully deterministic DashboardResponse from raw patient JSON.

    Used when Cohere is not configured or fails per-patient analysis.
    """
    insights: List[PatientInsight] = []
    high = med = low = 0
    worsening_count = 0
    variance_count = 0
    pending_inv = 0
    cohort_counts: Dict[str, int] = {}

    for idx, p in enumerate(patients):
        patient_id = p.get("patient_id", f"P-{idx+1:04d}")
        patient_name = p.get("name", "Unknown Patient")
        age = p.get("age", 0)
        gender = p.get("gender", "Unknown")

        referral = p.get("current_referral", {})
        history = p.get("history", {})
        visit_history = p.get("visit_history", [])
        call_history = p.get("call_history", [])
        advised = p.get("advised_actions", [])

        known_conditions = history.get("known_conditions", [])
        presenting = history.get("presenting_complaints", [])
        primary_condition = (
            presenting[0]["condition"]
            if presenting
            else (known_conditions[0] if known_conditions else "General Follow-up")
        )

        # Cohort
        dept = referral.get("department", "")
        cohort = _determine_cohort(dept, known_conditions, primary_condition)
        cohort_counts[cohort] = cohort_counts.get(cohort, 0) + 1

        # Risk
        risk = _determine_risk(visit_history, referral)
        if risk == RiskLevel.HIGH:
            high += 1
        elif risk == RiskLevel.MEDIUM:
            med += 1
        else:
            low += 1

        # Visit timeline
        timeline = [
            VisitSummary(
                visit_number=v_idx + 1,
                date=v.get("visit_date", ""),
                chief_complaint=v.get("chief_complaint", ""),
                doctor_note=v.get("examination", ""),
                medications_prescribed=v.get("prescription", []),
                labs_ordered=list(v.get("labs", {}).keys()) if v.get("labs") else [],
                vitals=v.get("vitals"),
            )
            for v_idx, v in enumerate(visit_history)
        ]

        # Progression
        progression = _determine_progression(visit_history)
        if progression == ProgressionStatus.WORSENING:
            worsening_count += 1

        # Conversion
        conversion = _determine_conversion(call_history, referral)

        # Pending counts
        pending_procs = sum(
            1 for a in advised
            if a.get("action_type") == "procedure" and a.get("status") == "pending"
        )
        pending_labs = sum(
            1 for a in advised
            if a.get("action_type") in ("lab", "radiology_test") and a.get("status") == "pending"
        )
        pending_refs = sum(
            1 for a in advised
            if a.get("action_type") == "referral" and a.get("status") == "pending"
        )
        pending_inv += pending_procs + pending_labs

        # Next actions
        next_actions = [
            NextAction(
                action=a.get("title", "Follow up"),
                reason=a.get("description", "As advised"),
                priority=1 if a.get("action_type") == "procedure" else 2,
                action_type=a.get("action_type", "follow_up"),
                source=SourceTrace(
                    type="visit_note",
                    description=a.get("description", "From clinical record"),
                    visit_number=len(visit_history),
                ),
            )
            for a in advised[:3]
        ] or [
            NextAction(
                action="Follow up",
                reason="Routine check",
                priority=3,
                action_type="follow_up",
                source=SourceTrace(
                    type="visit_note",
                    description="Scheduled follow-up",
                    visit_number=1,
                ),
            )
        ]

        summary_text = referral.get(
            "op_advised_reason",
            f"{patient_name}, {age}y {gender}, presenting with {primary_condition}.",
        )
        last_visit = (
            visit_history[-1].get("visit_date", "2024-01-01")
            if visit_history
            else "2024-01-01"
        )

        has_variance = _detect_variance(advised, call_history)
        if has_variance:
            variance_count += 1

        insights.append(
            PatientInsight(
                patient_id=patient_id,
                patient_name=patient_name,
                age=age,
                gender=gender,
                primary_condition=primary_condition.title(),
                cohort_bucket=cohort,
                risk_level=risk,
                risk_reasoning=_get_risk_reasoning(risk, visit_history, referral),
                progression_status=progression,
                care_path_variance=CarePathVariance(detected=has_variance, variances=[]),
                clinical_summary=summary_text,
                visit_timeline=timeline,
                progression_metrics=[],
                risk_flags=_extract_risk_flags(visit_history),
                next_actions=next_actions,
                conversion_status=conversion,
                pending_actions_summary=PendingActionsSummary(
                    pending_procedures=pending_procs,
                    pending_labs=pending_labs,
                    pending_referrals=pending_refs,
                ),
                suggested_priority_rank=idx + 1,
                last_visit_date=last_visit,
                days_since_last_visit=_days_since(last_visit),
            )
        )

    risk_order = {RiskLevel.HIGH: 0, RiskLevel.MEDIUM: 1, RiskLevel.LOW: 2}
    insights.sort(key=lambda x: risk_order.get(x.risk_level, 1))
    for rank, ins in enumerate(insights):
        ins.suggested_priority_rank = rank + 1

    summary = _build_summary(insights, len(patients), high, worsening_count, variance_count, pending_inv, cohort_counts)

    return DashboardResponse(
        summary=summary,
        patients=insights,
        generated_at=datetime.utcnow(),
        from_cache=False,
    )


# ─── Private helpers ───────────────────────────────────────────


def _determine_cohort(dept: str, conditions: list, primary: str) -> str:
    dept_l = dept.lower()
    cond_s = " ".join(c.lower() for c in conditions)
    prim_l = primary.lower()

    if "cardiol" in dept_l or "angina" in prim_l or "cardiac" in cond_s:
        return CohortBucket.CARDIAC_INTERVENTION_PENDING
    if "diabet" in cond_s or "hba1c" in prim_l:
        return CohortBucket.POORLY_CONTROLLED_DIABETIC
    if "hypertension" in cond_s or "htn" in cond_s:
        return CohortBucket.HTN_FOLLOWUP
    if "ckd" in cond_s or "kidney" in cond_s or "renal" in cond_s:
        return CohortBucket.CKD_FOLLOWUP
    if "neuro" in dept_l or "dystonia" in prim_l or "headache" in prim_l or "migrain" in prim_l:
        return CohortBucket.NEUROLOGICAL_DISORDER
    if "ortho" in dept_l or "arthro" in prim_l or "knee" in prim_l or "shoulder" in prim_l:
        return CohortBucket.MUSCULOSKELETAL_SURGICAL
    if "gastro" in dept_l or "gi" in prim_l or "liver" in cond_s or "hepat" in cond_s:
        return CohortBucket.GI_HEPATOBILIARY
    if len(conditions) >= 3:
        return CohortBucket.HIGH_RISK_MULTIMORBID
    if "post" in prim_l and "procedure" in prim_l:
        return CohortBucket.POST_PROCEDURE
    return CohortBucket.GENERAL_FOLLOWUP


def _determine_risk(visit_history: list, referral: dict) -> RiskLevel:
    if not visit_history:
        return RiskLevel.MEDIUM

    vitals = visit_history[-1].get("vitals", {})

    bp = vitals.get("bp", "")
    if bp:
        parts = bp.replace("/", " ").split()
        try:
            if int(parts[0]) > 160:
                return RiskLevel.HIGH
        except (ValueError, IndexError):
            pass

    hr = vitals.get("hr", 0)
    if isinstance(hr, (int, float)) and hr > 100:
        return RiskLevel.HIGH

    urgency = referral.get("op_advised_reason", "").lower()
    if any(w in urgency for w in ["urgent", "status migrain", "severe"]):
        return RiskLevel.HIGH

    return RiskLevel.MEDIUM


def _determine_progression(visit_history: list) -> ProgressionStatus:
    if len(visit_history) < 2:
        return ProgressionStatus.STABLE

    chief = visit_history[-1].get("chief_complaint", "").lower()
    if any(w in chief for w in ["worsening", "increasing", "persistent", "severe", "continuous"]):
        return ProgressionStatus.WORSENING
    if any(w in chief for w in ["improving", "better", "decreased", "resolved"]):
        return ProgressionStatus.IMPROVING
    if any(w in chief for w in ["recurrent", "recurring", "again"]):
        return ProgressionStatus.RECURRING
    return ProgressionStatus.STABLE


def _extract_risk_flags(visit_history: list) -> List[RiskFlag]:
    if not visit_history:
        return []

    flags: List[RiskFlag] = []
    latest = visit_history[-1]
    vitals = latest.get("vitals", {})
    labs = latest.get("labs", {})
    visit_num = len(visit_history)

    bp = vitals.get("bp", "")
    if bp:
        parts = bp.replace("/", " ").split()
        try:
            systolic = int(parts[0])
            if systolic > 150:
                flags.append(RiskFlag(
                    flag=f"Elevated BP: {bp}",
                    detail=f"Systolic {systolic} mmHg above safe threshold",
                    severity=RiskLevel.HIGH if systolic > 160 else RiskLevel.MEDIUM,
                    source=SourceTrace(type="vital", description=f"BP: {bp}", visit_number=visit_num),
                ))
        except (ValueError, IndexError):
            pass

    hba1c = labs.get("hba1c", 0)
    if isinstance(hba1c, (int, float)) and hba1c > 7.0:
        flags.append(RiskFlag(
            flag=f"HbA1c elevated: {hba1c}",
            detail=f"HbA1c {hba1c}% — above target threshold of 7.0%",
            severity=RiskLevel.HIGH if hba1c > 8.0 else RiskLevel.MEDIUM,
            source=SourceTrace(type="lab", description=f"HbA1c: {hba1c}%", visit_number=visit_num),
        ))

    creatinine = labs.get("creatinine", 0)
    if isinstance(creatinine, (int, float)) and creatinine > 1.2:
        flags.append(RiskFlag(
            flag=f"Creatinine elevated: {creatinine}",
            detail=f"Creatinine {creatinine} mg/dL — suggests renal concern",
            severity=RiskLevel.MEDIUM,
            source=SourceTrace(type="lab", description=f"Creatinine: {creatinine}", visit_number=visit_num),
        ))

    return flags


def _determine_conversion(call_history: list, referral: dict) -> ConversionStatus:
    procedure_advised = referral.get("op_advised", False)

    if not call_history:
        return ConversionStatus(procedure_advised=procedure_advised, admission_status="Pending", source=[])

    transcript = call_history[-1].get("transcript_summary", "").lower()
    detail = call_history[-1].get("transcript_summary", "")

    if any(w in transcript for w in ["declined", "not interested", "refuses", "declined admission"]):
        return ConversionStatus(
            procedure_advised=procedure_advised,
            admission_status="Declined",
            barrier="Patient declined",
            barrier_detail=detail,
            source=[SourceTrace(type="visit_note", description=detail[:100], visit_number=0)],
        )
    if any(w in transcript for w in ["insurance", "cost", "funds", "afford"]):
        return ConversionStatus(
            procedure_advised=procedure_advised,
            admission_status="Pending",
            barrier="Financial/Insurance barrier",
            barrier_detail=detail,
            source=[SourceTrace(type="visit_note", description="Financial concern noted", visit_number=0)],
        )
    if any(w in transcript for w in ["delay", "wait", "later", "managing", "physiotherapy"]):
        return ConversionStatus(
            procedure_advised=procedure_advised,
            admission_status="Pending",
            barrier="Patient deferring",
            barrier_detail=detail,
            source=[SourceTrace(type="visit_note", description="Patient wants to wait", visit_number=0)],
        )
    if any(w in transcript for w in ["interested", "agree", "ready", "proceed"]):
        return ConversionStatus(procedure_advised=procedure_advised, admission_status="In Progress", source=[])

    return ConversionStatus(procedure_advised=procedure_advised, admission_status="Pending", source=[])


def _detect_variance(advised: list, call_history: list) -> bool:
    """Return True if the patient has any care path variance."""
    today = datetime.utcnow().strftime("%Y-%m-%d")

    pending_count = sum(1 for a in advised if a.get("status") == "pending")
    if pending_count >= 2:
        return True

    for a in advised:
        if a.get("status") == "pending" and a.get("due_date") and a["due_date"] < today:
            return True

    no_answer_count = sum(1 for c in call_history if c.get("call_status") == "no_answer")
    if no_answer_count >= 2:
        return True

    barrier_keywords = [
        "declined", "not interested", "refuses", "insurance", "cost", "afford",
        "hometown", "delay", "wait", "later", "managing", "physiotherapy",
    ]
    return any(
        any(w in c.get("transcript_summary", "").lower() for w in barrier_keywords)
        for c in call_history
    )


def _get_risk_reasoning(risk: RiskLevel, visit_history: list, referral: dict) -> str:
    dept = referral.get("department", "")
    los = referral.get("estimated_los_days", 0)
    if risk == RiskLevel.HIGH:
        return (
            f"Patient flagged high-risk based on vitals and clinical urgency. "
            f"{dept} referral with estimated {los}-day stay."
        )
    if risk == RiskLevel.MEDIUM:
        return f"Moderate risk patient under {dept or 'specialist'} care with ongoing monitoring."
    return "Low risk — routine follow-up, stable vitals."


def _days_since(date_str: str) -> int:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return (datetime.utcnow() - d).days
    except Exception:
        return 0


def _build_summary(
    insights: List[PatientInsight],
    total: int,
    high: int,
    worsening: int,
    variance: int,
    pending_inv: int,
    cohort_counts: Dict[str, int],
) -> DashboardSummary:
    funnel_total = 0
    funnel_contacted = 0
    funnel_interested = 0
    funnel_converted = 0
    funnel_declined = 0

    for ins in insights:
        if ins.conversion_status.procedure_advised:
            funnel_total += 1
        status = ins.conversion_status.admission_status
        if status in ("Converted", "In Progress", "Declined"):
            funnel_contacted += 1
        if status == "In Progress":
            funnel_interested += 1
        elif status == "Converted":
            funnel_converted += 1
        elif status == "Declined":
            funnel_declined += 1

    funnel_pending = max(0, funnel_contacted - funnel_interested - funnel_converted - funnel_declined)

    return DashboardSummary(
        total_patients=total,
        high_risk_count=high,
        worsening_count=worsening,
        care_path_variance_count=variance,
        pending_investigations=pending_inv,
        cohort_distribution=cohort_counts,
        conversion_funnel=ConversionFunnelSummary(
            total_advised=funnel_total,
            contacted=funnel_contacted,
            interested=funnel_interested,
            converted=funnel_converted,
            declined=funnel_declined,
            pending=funnel_pending,
        ),
    )
