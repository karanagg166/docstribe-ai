import React from "react";
import { SourceTrace } from "@/types/patient";
import { FileText, Activity, Pill, Clipboard } from "lucide-react";

export default function SourceTraceBadge({ trace }: { trace: SourceTrace }) {
  const getIcon = () => {
    switch(trace.type) {
      case "vital": return <Activity size={12} />;
      case "prescription": return <Pill size={12} />;
      case "visit_note": return <Clipboard size={12} />;
      case "lab": return <FileText size={12} />;
      default: return <FileText size={12} />;
    }
  };

  return (
    <div className="group relative inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500 hover:bg-slate-200 transition-colors cursor-help">
      {getIcon()}
      <span>Source</span>
      {trace.visit_number && <span className="text-slate-400">V{trace.visit_number}</span>}
      
      {/* Tooltip */}
      <div className="absolute bottom-full left-1/2 z-50 mb-2 -translate-x-1/2 whitespace-nowrap rounded bg-slate-800 px-2 py-1 text-xs text-white opacity-0 transition-opacity group-hover:opacity-100 pointer-events-none">
        {trace.description}
        {/* Arrow */}
        <div className="absolute left-1/2 top-full -translate-x-1/2 border-4 border-transparent border-t-slate-800"></div>
      </div>
    </div>
  );
}
