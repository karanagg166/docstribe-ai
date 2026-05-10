"""Deterministic fallback engine for clinical insights.

Used when Cohere is unavailable or returns an invalid response.
All functions here are pure Python — no LLM calls.
"""

from datetime import datetime
from typing import Any, Dict, List

from app.models.schemas import (
    CarePathVariance,
    ConversionFunnelSummary,
    ConversionStatus,
    DashboardResponse,
    DashboardSummary,
    NextAction,
    PatientInsight,
    PendingActionsSummary,
    ProgressionPoint,
    ProgressionStatus,
    RiskFlag,
    RiskLevel,
    SourceTrace,
    VarianceDetail,
    VisitSummary,
)
from app.services.clinical_rules import (
    VITAL_THRESHOLDS,
    LAB_THRESHOLDS,
    TRACKABLE_VITALS,
    MULTI_MORBID_CONDITION_COUNT,
    URGENCY_KEYWORDS,
    CONVERSION_DECLINED_KEYWORDS,
    CONVERSION_FINANCIAL_KEYWORDS,
    CONVERSION_DEFERRING_KEYWORDS,
    CONVERSION_POSITIVE_KEYWORDS,
    WORSENING_KEYWORDS,
    IMPROVING_KEYWORDS,
    RECURRING_KEYWORDS,
    DEFAULT_COHORT,
    MULTI_MORBID_COHORT,
    match_cohort,
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
        risk = _determine_risk(visit_history, referral, known_conditions)
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

        variances = _build_variances(advised, call_history)
        if variances:
            variance_count += 1

        prog_metrics = _extract_progression_metrics(visit_history)

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
                care_path_variance=CarePathVariance(detected=bool(variances), variances=variances),
                clinical_summary=summary_text,
                visit_timeline=timeline,
                progression_metrics=prog_metrics,
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
    return match_cohort(dept_l, cond_s, prim_l, len(conditions))


def _determine_risk(visit_history: list, referral: dict, known_conditions: list | None = None) -> RiskLevel:
    if not visit_history:
        return RiskLevel.MEDIUM

    # Check ALL visits — worst-case vitals win
    for visit in visit_history:
        vitals = visit.get("vitals", {})

        bp = vitals.get("bp", "")
        if bp:
            parts = bp.replace("/", " ").split()
            try:
                if int(parts[0]) > VITAL_THRESHOLDS["bp_systolic_high"]:
                    return RiskLevel.HIGH
            except (ValueError, IndexError):
                pass

        hr = vitals.get("hr", 0)
        if isinstance(hr, (int, float)) and hr > VITAL_THRESHOLDS["hr_high"]:
            return RiskLevel.HIGH

        spo2 = vitals.get("spo2")
        if isinstance(spo2, (int, float)) and spo2 < VITAL_THRESHOLDS["spo2_low"]:
            return RiskLevel.HIGH

        temp = vitals.get("temp_f")
        if isinstance(temp, (int, float)) and temp > VITAL_THRESHOLDS["temp_f_high"]:
            return RiskLevel.HIGH

    # Comorbidity check
    conditions = known_conditions or []
    if len(conditions) >= MULTI_MORBID_CONDITION_COUNT:
        return RiskLevel.HIGH

    urgency = referral.get("op_advised_reason", "").lower()
    if any(w in urgency for w in URGENCY_KEYWORDS):
        return RiskLevel.HIGH

    return RiskLevel.MEDIUM


def _determine_progression(visit_history: list) -> ProgressionStatus:
    if len(visit_history) < 2:
        return ProgressionStatus.STABLE

    # 1. Numerical vital trend: compare systolic BP across visits
    systolics = []
    for v in visit_history:
        bp = v.get("vitals", {}).get("bp", "")
        if bp:
            try:
                systolics.append(int(bp.replace("/", " ").split()[0]))
            except (ValueError, IndexError):
                pass

    bp_cfg = TRACKABLE_VITALS.get("bp", {})
    bp_delta = bp_cfg.get("delta", 5)
    if len(systolics) >= 2:
        if systolics[-1] < systolics[0] - bp_delta:
            return ProgressionStatus.IMPROVING
        if systolics[-1] > systolics[0] + bp_delta:
            return ProgressionStatus.WORSENING

    # 2. Generic lab trend: check ALL configured labs, first worsening signal wins
    for lab_key, cfg in LAB_THRESHOLDS.items():
        vals = []
        for v in visit_history:
            val = v.get("labs", {}).get(lab_key)
            if isinstance(val, (int, float)):
                vals.append(float(val))
        if len(vals) >= 2:
            delta = cfg.get("delta", 0.2)
            direction = cfg.get("direction", "high_is_bad")
            if direction == "high_is_bad":
                if vals[-1] > vals[0] + delta:
                    return ProgressionStatus.WORSENING
                if vals[-1] < vals[0] - delta:
                    return ProgressionStatus.IMPROVING
            else:  # low_is_bad
                if vals[-1] < vals[0] - delta:
                    return ProgressionStatus.WORSENING
                if vals[-1] > vals[0] + delta:
                    return ProgressionStatus.IMPROVING

    # 3. Keyword fallback on chief complaint
    chief = visit_history[-1].get("chief_complaint", "").lower()
    if any(w in chief for w in WORSENING_KEYWORDS):
        return ProgressionStatus.WORSENING
    if any(w in chief for w in IMPROVING_KEYWORDS):
        return ProgressionStatus.IMPROVING
    if any(w in chief for w in RECURRING_KEYWORDS):
        return ProgressionStatus.RECURRING
    return ProgressionStatus.STABLE


def _extract_risk_flags(visit_history: list) -> List[RiskFlag]:
    if not visit_history:
        return []

    flags: List[RiskFlag] = []
    seen: set = set()  # Avoid duplicate flag types

    for v_idx, visit in enumerate(visit_history):
        vitals = visit.get("vitals", {})
        labs = visit.get("labs", {})
        visit_num = v_idx + 1

        # BP check
        bp = vitals.get("bp", "")
        if bp and "bp" not in seen:
            parts = bp.replace("/", " ").split()
            try:
                systolic = int(parts[0])
                if systolic > VITAL_THRESHOLDS["bp_systolic_elevated"]:
                    seen.add("bp")
                    flags.append(RiskFlag(
                        flag=f"Elevated BP: {bp}",
                        detail=f"Systolic {systolic} mmHg above safe threshold (Visit {visit_num})",
                        severity=RiskLevel.HIGH if systolic > VITAL_THRESHOLDS["bp_systolic_high"] else RiskLevel.MEDIUM,
                        source=SourceTrace(type="vital", description=f"BP: {bp}", visit_number=visit_num),
                    ))
            except (ValueError, IndexError):
                pass

        # SpO2 check
        spo2 = vitals.get("spo2")
        if isinstance(spo2, (int, float)) and spo2 < VITAL_THRESHOLDS["spo2_low"] and "spo2" not in seen:
            seen.add("spo2")
            flags.append(RiskFlag(
                flag=f"Low SpO2: {spo2}%",
                detail=f"SpO2 {spo2}% indicates hypoxemia (Visit {visit_num})",
                severity=RiskLevel.HIGH,
                source=SourceTrace(type="vital", description=f"SpO2: {spo2}%", visit_number=visit_num),
            ))

        # Temperature check
        temp = vitals.get("temp_f")
        if isinstance(temp, (int, float)) and temp > VITAL_THRESHOLDS["temp_f_high"] and "temp" not in seen:
            seen.add("temp")
            flags.append(RiskFlag(
                flag=f"Fever: {temp}°F",
                detail=f"Temperature {temp}°F above {VITAL_THRESHOLDS['temp_f_high']}°F threshold (Visit {visit_num})",
                severity=RiskLevel.HIGH,
                source=SourceTrace(type="vital", description=f"Temp: {temp}°F", visit_number=visit_num),
            ))

        # Generic lab checks — auto-flag ANY lab that exceeds its configured threshold
        for lab_key, cfg in LAB_THRESHOLDS.items():
            if lab_key in seen:
                continue
            val = labs.get(lab_key)
            if not isinstance(val, (int, float)):
                continue
            elevated = cfg.get("elevated")
            critical = cfg.get("critical")
            direction = cfg.get("direction", "high_is_bad")
            display = cfg.get("display_name", lab_key.replace("_", " ").title())
            unit = cfg.get("unit", "")

            is_flagged = False
            if direction == "high_is_bad" and elevated and val > elevated:
                is_flagged = True
                severity = RiskLevel.HIGH if (critical and val > critical) else RiskLevel.MEDIUM
            elif direction == "low_is_bad":
                low_thresh = cfg.get("low_threshold", elevated)
                if low_thresh and val < low_thresh:
                    is_flagged = True
                    severity = RiskLevel.HIGH if (critical and val < critical) else RiskLevel.MEDIUM

            if is_flagged:
                seen.add(lab_key)
                flags.append(RiskFlag(
                    flag=f"{display} abnormal: {val}{unit}",
                    detail=f"{display} {val}{unit} — outside safe range (Visit {visit_num})",
                    severity=severity,
                    source=SourceTrace(type="lab", description=f"{display}: {val}{unit}", visit_number=visit_num),
                ))

    return flags


def _determine_conversion(call_history: list, referral: dict) -> ConversionStatus:
    procedure_advised = referral.get("op_advised", False)

    if not call_history:
        return ConversionStatus(procedure_advised=procedure_advised, admission_status="Pending", source=[])

    no_answer_count = 0
    for call in call_history:
        outcome = call.get("outcome", call.get("call_status", "")).lower()
        if outcome in ["no_answer", "no answer", "not_connected", "switched_off"]:
            no_answer_count += 1
            
    if no_answer_count >= 2:
        return ConversionStatus(
            procedure_advised=procedure_advised,
            admission_status="Pending",
            barrier="Unreachable",
            barrier_detail=f"Patient unreachable ({no_answer_count} failed contact attempts)",
            source=[SourceTrace(type="visit_note", description="Multiple failed contact attempts", visit_number=0)],
        )

    transcript = call_history[-1].get("transcript_summary", "").lower()
    detail = call_history[-1].get("transcript_summary", "")

    if any(w in transcript for w in CONVERSION_DECLINED_KEYWORDS):
        return ConversionStatus(
            procedure_advised=procedure_advised,
            admission_status="Declined",
            barrier="Patient declined",
            barrier_detail=detail,
            source=[SourceTrace(type="visit_note", description=detail[:100], visit_number=0)],
        )
    if any(w in transcript for w in CONVERSION_FINANCIAL_KEYWORDS):
        return ConversionStatus(
            procedure_advised=procedure_advised,
            admission_status="Pending",
            barrier="Financial/Insurance barrier",
            barrier_detail=detail,
            source=[SourceTrace(type="visit_note", description="Financial concern noted", visit_number=0)],
        )
    if any(w in transcript for w in CONVERSION_DEFERRING_KEYWORDS):
        return ConversionStatus(
            procedure_advised=procedure_advised,
            admission_status="Pending",
            barrier="Patient deferring",
            barrier_detail=detail,
            source=[SourceTrace(type="visit_note", description="Patient wants to wait", visit_number=0)],
        )
    if any(w in transcript for w in CONVERSION_POSITIVE_KEYWORDS):
        return ConversionStatus(procedure_advised=procedure_advised, admission_status="In Progress", source=[])

    return ConversionStatus(procedure_advised=procedure_advised, admission_status="Pending", source=[])


def _build_variances(advised: list, call_history: list) -> List[VarianceDetail]:
    """Return populated VarianceDetail objects for all detected care path variances."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    variances: List[VarianceDetail] = []

    # Overdue pending actions
    for a in advised:
        if a.get("status") == "pending" and a.get("due_date") and a["due_date"] < today:
            variances.append(VarianceDetail(
                description=f"{a.get('title', 'Action')} overdue since {a['due_date']}",
                expected_action=f"{a.get('title', 'Action')} completed by {a['due_date']}",
                actual_finding=f"Still pending as of {today}",
                source=[SourceTrace(type="visit_note", description=a.get("description", ""), visit_number=0)],
            ))

    # Multiple pending procedures/admissions
    pending_procs = [a for a in advised if a.get("status") == "pending" and a.get("action_type") in ("procedure", "ip_admission")]
    if len(pending_procs) >= 2 and not variances:
        variances.append(VarianceDetail(
            description=f"{len(pending_procs)} procedures/admissions still pending",
            expected_action="Procedures scheduled and completed per clinical plan",
            actual_finding=f"{len(pending_procs)} items remain pending",
            source=[SourceTrace(type="visit_note", description=p.get("title", ""), visit_number=0) for p in pending_procs[:2]],
        ))

    # Call-based variances
    no_answer_count = 0
    for call in call_history:
        outcome = str(call.get("outcome", "")).lower()
        call_status = str(call.get("call_status", "")).lower()
        summary = str(call.get("summary", call.get("transcript_summary", ""))).lower()
        call_date = call.get("date", call.get("call_date", ""))

        if outcome in ("no_answer", "no answer") or call_status == "no_answer":
            no_answer_count += 1
            continue

        # Decline detection — exclude financial/insurance/deferral reasons
        if any(kw in summary for kw in CONVERSION_DECLINED_KEYWORDS):
            is_financial_or_deferral = any(
                fkw in summary for fkw in CONVERSION_FINANCIAL_KEYWORDS + CONVERSION_DEFERRING_KEYWORDS
            )
            if not is_financial_or_deferral:
                variances.append(VarianceDetail(
                    description="Patient declined advised treatment/admission",
                    expected_action="Patient proceeds with clinical recommendation",
                    actual_finding=f"Call on {call_date}: Patient expressed refusal (non-financial)",
                    source=[SourceTrace(type="visit_note", description=f"Call log: {summary[:80]}", visit_number=0)],
                ))

    if no_answer_count >= 2:
        variances.append(VarianceDetail(
            description="Patient unreachable — multiple call attempts unanswered",
            expected_action="Patient contacted for follow-up coordination",
            actual_finding=f"{no_answer_count} calls went unanswered",
            source=[SourceTrace(type="visit_note", description="Call log", visit_number=0)],
        ))

    # NOTE: Financial/insurance barriers and patient deferral are tracked
    # via conversion_status, NOT as clinical variances.

    return variances


def _get_risk_reasoning(risk: RiskLevel, visit_history: list, referral: dict) -> str:
    """Generate specific risk reasoning citing actual abnormal values."""
    reasons: List[str] = []

    for v_idx, visit in enumerate(visit_history):
        vitals = visit.get("vitals", {})
        labs = visit.get("labs", {})
        vn = v_idx + 1

        bp = vitals.get("bp", "")
        if bp:
            try:
                systolic = int(bp.replace("/", " ").split()[0])
                if systolic > VITAL_THRESHOLDS["bp_systolic_elevated"]:
                    reasons.append(f"BP {bp} in Visit {vn} exceeds threshold")
            except (ValueError, IndexError):
                pass

        spo2 = vitals.get("spo2")
        if isinstance(spo2, (int, float)) and spo2 < VITAL_THRESHOLDS["spo2_low"]:
            reasons.append(f"SpO2 {spo2}% in Visit {vn} indicates hypoxemia")

        # Generic lab reasoning
        for lab_key, cfg in LAB_THRESHOLDS.items():
            val = labs.get(lab_key)
            if not isinstance(val, (int, float)):
                continue
            elevated = cfg.get("elevated")
            display = cfg.get("display_name", lab_key)
            if elevated and val > elevated:
                reasons.append(f"{display} {val} in Visit {vn} above {elevated} target")

    if not reasons:
        dept = referral.get("department", "specialist")
        if risk == RiskLevel.HIGH:
            reasons.append(f"Clinical urgency noted in {dept} referral")
        elif risk == RiskLevel.MEDIUM:
            return f"Moderate risk patient under {dept} care with ongoing monitoring."
        else:
            return "Low risk — routine follow-up, stable vitals."

    return "; ".join(reasons[:3]) + "."


def _extract_progression_metrics(visit_history: list) -> List[ProgressionPoint]:
    """Build ProgressionPoint objects from longitudinal lab/vital data — fully generic."""
    metrics: List[ProgressionPoint] = []

    # 1. Systolic BP trend (vital — special extraction from string)
    bp_points = []
    for v_idx, v in enumerate(visit_history):
        bp = v.get("vitals", {}).get("bp", "")
        if bp:
            try:
                systolic = int(bp.replace("/", " ").split()[0])
                bp_points.append({"date": v.get("visit_date", f"Visit {v_idx+1}"), "value": str(systolic)})
            except (ValueError, IndexError):
                pass
    if len(bp_points) >= 2:
        bp_cfg = TRACKABLE_VITALS.get("bp", {})
        bp_delta = bp_cfg.get("delta", 5)
        first, last = int(bp_points[0]["value"]), int(bp_points[-1]["value"])
        trend = ProgressionStatus.IMPROVING if last < first - bp_delta else (ProgressionStatus.WORSENING if last > first + bp_delta else ProgressionStatus.STABLE)
        metrics.append(ProgressionPoint(
            metric="Systolic BP", values=bp_points, trend=trend,
            source=SourceTrace(type="vital", description="BP trend across visits", visit_number=len(visit_history)),
        ))

    # 2. Generic lab trends — auto-discover ALL labs present in LAB_THRESHOLDS
    for lab_key, cfg in LAB_THRESHOLDS.items():
        points = []
        for v_idx, v in enumerate(visit_history):
            val = v.get("labs", {}).get(lab_key)
            if isinstance(val, (int, float)):
                points.append({"date": v.get("visit_date", f"Visit {v_idx+1}"), "value": str(val)})
        if len(points) >= 2:
            delta = cfg.get("delta", 0.2)
            direction = cfg.get("direction", "high_is_bad")
            display = cfg.get("display_name", lab_key.replace("_", " ").title())
            first, last = float(points[0]["value"]), float(points[-1]["value"])
            if direction == "high_is_bad":
                trend = ProgressionStatus.IMPROVING if last < first - delta else (ProgressionStatus.WORSENING if last > first + delta else ProgressionStatus.STABLE)
            else:
                trend = ProgressionStatus.WORSENING if last < first - delta else (ProgressionStatus.IMPROVING if last > first + delta else ProgressionStatus.STABLE)
            metrics.append(ProgressionPoint(
                metric=display, values=points, trend=trend,
                source=SourceTrace(type="lab", description=f"{display} trend across visits", visit_number=len(visit_history)),
            ))

    return metrics


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

    funnel_pending = max(0, funnel_total - funnel_contacted)

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
