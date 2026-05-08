from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

# ─── Enums ───────────────────────────────────────────

class RiskLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ProgressionStatus(str, Enum):
    WORSENING = "worsening"
    IMPROVING = "improving"
    STABLE = "stable"
    RECURRING = "recurring"

class CohortBucket(str, Enum):
    POORLY_CONTROLLED_DIABETIC = "Poorly Controlled Diabetic"
    HTN_FOLLOWUP = "Hypertension Follow-up"
    CKD_FOLLOWUP = "CKD Follow-up"
    RECURRENT_INFECTION = "Recurrent Infection"
    POST_PROCEDURE = "Post-Procedure Recovery"
    HIGH_UTILIZATION = "High Utilization OPD"
    GENERAL_FOLLOWUP = "General Follow-up"
    CARDIAC_INTERVENTION_PENDING = "Cardiac Intervention Pending"
    NEUROLOGICAL_DISORDER = "Neurological/Movement Disorder"
    MUSCULOSKELETAL_SURGICAL = "Musculoskeletal/Surgical"
    GI_HEPATOBILIARY = "GI/Hepatobiliary"
    HIGH_RISK_MULTIMORBID = "High-Risk Multi-Morbid"

# ─── Source Trace ─────────────────────────────────────

class SourceTrace(BaseModel):
    type: str                   # "lab", "visit_note", "prescription", "vital"
    description: str            # "HbA1c: 8.9 — Lab report Apr 2025"
    visit_number: Optional[int] = None

# ─── Risk Flag ────────────────────────────────────────

class RiskFlag(BaseModel):
    flag: str                   # "HbA1c critically high"
    detail: str                 # "8.9 — above safe threshold"
    severity: RiskLevel
    source: SourceTrace

# ─── Next Action ──────────────────────────────────────

class NextAction(BaseModel):
    action: str                 # "Urgent nephrology referral"
    reason: str                 # "Creatinine rising over 3 visits"
    priority: int               # 1 = most urgent
    action_type: str            # "clinical", "operational", "investigative", "follow_up"
    source: SourceTrace

# ─── Progression Point ────────────────────────────────

class ProgressionPoint(BaseModel):
    metric: str                 # "HbA1c"
    values: List[dict]          # [{"date": "Dec 2024", "value": "7.2"}]
    trend: ProgressionStatus
    source: SourceTrace

# ─── Care Path Variance ───────────────────────────────

class VarianceDetail(BaseModel):
    description: str            # "Nephrology referral suggested but not done"
    expected_action: str        # "Referral after creatinine >1.2"
    actual_finding: str         # "No referral record in Visit 3"
    source: List[SourceTrace]

class CarePathVariance(BaseModel):
    detected: bool
    variances: List[VarianceDetail] = []

# ─── Visit Summary ────────────────────────────────────

class VisitSummary(BaseModel):
    visit_number: int
    date: str
    chief_complaint: str
    doctor_note: Optional[str] = None
    medications_prescribed: List[str] = []
    labs_ordered: List[str] = []
    vitals: Optional[dict] = None

# ─── Conversion Status ────────────────────────────────

class ConversionStatus(BaseModel):
    procedure_advised: bool
    admission_status: str       # "Pending", "In Progress", "Declined", "Converted"
    barrier: Optional[str] = None
    barrier_detail: Optional[str] = None
    source: List[SourceTrace] = []

# ─── Pending Actions Summary ──────────────────────────

class PendingActionsSummary(BaseModel):
    pending_procedures: int = 0
    pending_labs: int = 0
    pending_referrals: int = 0

# ─── Full Patient Insight (LLM Output) ───────────────

class PatientInsight(BaseModel):
    patient_id: str
    patient_name: str
    age: int
    gender: str
    primary_condition: str
    cohort_bucket: CohortBucket
    risk_level: RiskLevel
    risk_reasoning: str
    progression_status: ProgressionStatus
    care_path_variance: CarePathVariance
    clinical_summary: str           # 3-5 line LLM summary
    visit_timeline: List[VisitSummary]
    progression_metrics: List[ProgressionPoint]
    risk_flags: List[RiskFlag]
    next_actions: List[NextAction]
    conversion_status: ConversionStatus
    pending_actions_summary: PendingActionsSummary
    suggested_priority_rank: int
    last_visit_date: str
    days_since_last_visit: int

# ─── Conversion Funnel Summary ───────────────────────

class ConversionFunnelSummary(BaseModel):
    total_advised: int = 0         # patients with procedure/admission advised
    contacted: int = 0             # patients with at least 1 call
    interested: int = 0            # showed interest in calls
    converted: int = 0             # agreed / admitted
    declined: int = 0              # explicitly refused
    pending: int = 0               # unclear / no decision yet

# ─── Dashboard Summary (for cards) ───────────────────

class DashboardSummary(BaseModel):
    total_patients: int
    high_risk_count: int
    worsening_count: int
    care_path_variance_count: int
    pending_investigations: int
    cohort_distribution: dict      # {"Poorly Controlled Diabetic": 2, ...}
    conversion_funnel: ConversionFunnelSummary = ConversionFunnelSummary()

# ─── API Response ─────────────────────────────────────

class DashboardResponse(BaseModel):
    summary: DashboardSummary
    patients: List[PatientInsight]
    generated_at: datetime
    from_cache: bool