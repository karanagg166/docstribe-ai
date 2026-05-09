export type RiskLevel = "high" | "medium" | "low"
export type ProgressionStatus = "worsening" | "improving" | "stable" | "recurring"

export interface SourceTrace {
    type: "lab" | "visit_note" | "prescription" | "vital"
    description: string
    visit_number?: number
}

export interface RiskFlag {
    flag: string
    detail: string
    severity: RiskLevel
    source: SourceTrace
}

export interface NextAction {
    action: string
    reason: string
    priority: number
    action_type: string
    source: SourceTrace
}

export interface ProgressionPoint {
    metric: string
    values: { date: string; value: string }[]
    trend: ProgressionStatus
    source: SourceTrace
}

export interface VarianceDetail {
    description: string
    expected_action: string
    actual_finding: string
    source: SourceTrace[]
}

export interface CarePathVariance {
    detected: boolean
    variances: VarianceDetail[]
}

export interface VisitSummary {
    visit_number: number
    date: string
    chief_complaint: string
    doctor_note?: string
    medications_prescribed: string[]
    labs_ordered: string[]
    vitals?: Record<string, string>
}

export interface ConversionStatus {
    procedure_advised: boolean
    admission_status: string
    barrier?: string
    barrier_detail?: string
    source: SourceTrace[]
}

export interface PendingActionsSummary {
    pending_procedures: number
    pending_labs: number
    pending_referrals: number
}

export interface PatientInsight {
    patient_id: string
    patient_name: string
    age: number
    gender: string
    primary_condition: string
    cohort_bucket: string
    risk_level: RiskLevel
    risk_reasoning: string
    progression_status: ProgressionStatus
    care_path_variance: CarePathVariance
    clinical_summary: string
    visit_timeline: VisitSummary[]
    progression_metrics: ProgressionPoint[]
    risk_flags: RiskFlag[]
    next_actions: NextAction[]
    conversion_status: ConversionStatus
    pending_actions_summary: PendingActionsSummary
    suggested_priority_rank: number
    last_visit_date: string
    days_since_last_visit: number
}

export interface ConversionFunnelSummary {
    total_advised: number
    contacted: number
    interested: number
    converted: number
    declined: number
    pending: number
}

export interface DashboardSummary {
    total_patients: number
    high_risk_count: number
    worsening_count: number
    care_path_variance_count: number
    pending_investigations: number
    conversion_barrier_count?: number
    pending_procedures_count?: number
    cohort_distribution: Record<string, number>
    conversion_funnel: ConversionFunnelSummary
}

export interface DashboardResponse {
    summary: DashboardSummary
    patients: PatientInsight[]
    generated_at: string
    from_cache: boolean
}