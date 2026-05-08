import React from "react";
import { PatientInsight } from "@/types/patient";
import { usePatientDetail } from "@/hooks/usePatientDetail";
import { getRiskBgClass, getCohortColorClass } from "@/lib/utils";
import { ChevronRight, TrendingUp, TrendingDown, Minus, RefreshCw, AlertCircle } from "lucide-react";

export default function PatientWorklist({ patients }: { patients: PatientInsight[] }) {
  const { openPanel } = usePatientDetail();

  if (patients.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="rounded-full bg-slate-100 p-3 mb-4">
          <SearchX className="h-6 w-6 text-slate-400" />
        </div>
        <h3 className="text-sm font-medium text-slate-900">No patients found</h3>
        <p className="mt-1 text-sm text-slate-500">Try adjusting your filters or search query.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm whitespace-nowrap">
        <thead className="bg-slate-50 text-slate-500 border-b border-[var(--color-border)]">
          <tr>
            <th className="px-4 py-3 font-medium">Rank</th>
            <th className="px-4 py-3 font-medium">Patient</th>
            <th className="px-4 py-3 font-medium">Condition</th>
            <th className="px-4 py-3 font-medium">Cohort</th>
            <th className="px-4 py-3 font-medium">Risk</th>
            <th className="px-4 py-3 font-medium">Trend</th>
            <th className="px-4 py-3 font-medium">Variances</th>
            <th className="px-4 py-3 font-medium text-right">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--color-border)] bg-white">
          {patients.map((patient) => (
            <PatientRow 
              key={patient.patient_id} 
              patient={patient} 
              onClick={() => openPanel(patient)} 
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PatientRow({ patient, onClick }: { patient: PatientInsight, onClick: () => void }) {
  const getTrendIcon = () => {
    switch(patient.progression_status) {
      case "worsening": return <TrendingUp size={14} className="text-rose-600" />;
      case "improving": return <TrendingDown size={14} className="text-emerald-600" />;
      case "stable": return <Minus size={14} className="text-blue-600" />;
      case "recurring": return <RefreshCw size={14} className="text-amber-600" />;
      default: return null;
    }
  };

  return (
    <tr 
      onClick={onClick}
      className="cursor-pointer transition-colors hover:bg-slate-50 group"
    >
      <td className="px-4 py-4">
        <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-xs font-medium text-slate-600 group-hover:bg-primary group-hover:text-white transition-colors">
          {patient.suggested_priority_rank}
        </span>
      </td>
      <td className="px-4 py-4">
        <div className="font-medium text-slate-900">{patient.patient_name}</div>
        <div className="text-xs text-slate-500">{patient.patient_id} • {patient.age}y {patient.gender.charAt(0)}</div>
      </td>
      <td className="px-4 py-4 text-slate-600 max-w-[200px] truncate" title={patient.primary_condition}>
        {patient.primary_condition}
      </td>
      <td className="px-4 py-4">
        <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ${getCohortColorClass(patient.cohort_bucket)}`}>
          {patient.cohort_bucket}
        </span>
      </td>
      <td className="px-4 py-4">
        <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ${getRiskBgClass(patient.risk_level)} capitalize`}>
          {patient.risk_level}
        </span>
      </td>
      <td className="px-4 py-4">
        <div className="flex items-center gap-1.5 capitalize text-slate-600">
          {getTrendIcon()}
          <span>{patient.progression_status}</span>
        </div>
      </td>
      <td className="px-4 py-4">
        {patient.care_path_variance.detected ? (
          <span className="inline-flex items-center gap-1 text-rose-600">
            <AlertCircle size={14} />
            <span className="text-xs font-medium">{patient.care_path_variance.variances.length} Variance(s)</span>
          </span>
        ) : (
          <span className="text-slate-400 text-xs">None</span>
        )}
      </td>
      <td className="px-4 py-4 text-right">
        <button className="inline-flex items-center justify-center text-slate-400 group-hover:text-primary transition-colors">
          <ChevronRight size={18} />
        </button>
      </td>
    </tr>
  );
}

// Temporary inline for missing icon
function SearchX(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m13.5 8.5-5 5" />
      <path d="m8.5 8.5 5 5" />
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  )
}
