import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function getRiskColor(risk: "high" | "medium" | "low"): string {
  switch (risk) {
    case "high":
      return "var(--color-risk-high)";
    case "medium":
      return "var(--color-risk-medium)";
    case "low":
      return "var(--color-risk-low)";
    default:
      return "var(--color-text-muted)";
  }
}

export function getRiskBgClass(risk: "high" | "medium" | "low"): string {
  switch (risk) {
    case "high":
      return "bg-rose-100 text-rose-700 border-rose-200";
    case "medium":
      return "bg-amber-100 text-amber-700 border-amber-200";
    case "low":
      return "bg-emerald-100 text-emerald-700 border-emerald-200";
    default:
      return "bg-slate-100 text-slate-700 border-slate-200";
  }
}

export function getCohortColorClass(cohort: string): string {
  // Simple deterministic color map
  const colors = [
    "bg-blue-100 text-blue-700 border-blue-200",
    "bg-indigo-100 text-indigo-700 border-indigo-200",
    "bg-violet-100 text-violet-700 border-violet-200",
    "bg-purple-100 text-purple-700 border-purple-200",
    "bg-fuchsia-100 text-fuchsia-700 border-fuchsia-200",
    "bg-pink-100 text-pink-700 border-pink-200",
  ];
  
  let hash = 0;
  for (let i = 0; i < cohort.length; i++) {
    hash = cohort.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}
