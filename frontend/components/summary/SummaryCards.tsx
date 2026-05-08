import React from "react";
import { Users, AlertTriangle, TrendingDown, ClipboardList, Stethoscope, PhoneForwarded } from "lucide-react";
import { DashboardSummary } from "@/types/patient";

export default function SummaryCards({ summary }: { summary: DashboardSummary }) {
  const cards = [
    {
      title: "Total OPD Patients",
      value: summary.total_patients,
      icon: Users,
      color: "text-blue-600",
      bg: "bg-blue-50",
    },
    {
      title: "High Risk Cases",
      value: summary.high_risk_count,
      icon: AlertTriangle,
      color: "text-rose-600",
      bg: "bg-rose-50",
      pulse: true,
    },
    {
      title: "Worsening Trends",
      value: summary.worsening_count,
      icon: TrendingDown,
      color: "text-amber-600",
      bg: "bg-amber-50",
    },
    {
      title: "Care Path Variances",
      value: summary.care_path_variance_count,
      icon: ClipboardList,
      color: "text-indigo-600",
      bg: "bg-indigo-50",
    },
    {
      title: "Pending Procedures",
      value: summary.pending_procedures_count || summary.pending_investigations,
      icon: Stethoscope,
      color: "text-violet-600",
      bg: "bg-violet-50",
    },
    {
      title: "Conversion Barriers",
      value: summary.conversion_barrier_count || 0,
      icon: PhoneForwarded,
      color: "text-fuchsia-600",
      bg: "bg-fuchsia-50",
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      {cards.map((card, idx) => (
        <div key={idx} className="glass-card flex items-center justify-between rounded-xl p-4 transition-all hover:shadow-md cursor-pointer hover:-translate-y-0.5">
          <div>
            <p className="text-xs font-medium text-[var(--color-text-muted)]">{card.title}</p>
            <p className="mt-1 text-2xl font-semibold text-[var(--color-text-main)]">{card.value}</p>
          </div>
          <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${card.bg} ${card.color} ${card.pulse ? 'animate-pulse-soft' : ''}`}>
            <card.icon size={20} />
          </div>
        </div>
      ))}
    </div>
  );
}
