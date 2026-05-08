import React from "react";
import { Activity } from "lucide-react";

export default function DashboardShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[var(--color-background)]">
      {/* Top Navigation */}
      <header className="sticky top-0 z-30 w-full border-b border-[var(--color-border)] bg-white/80 backdrop-blur-md">
        <div className="flex h-16 items-center justify-between px-6">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-primary)] text-white">
              <Activity size={18} />
            </div>
            <span className="text-xl font-semibold tracking-tight text-[var(--color-text-main)]">
              Docstribe AI
            </span>
            <span className="ml-2 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
              OPD Triage
            </span>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-sm text-[var(--color-text-muted)]">
              <span className="flex h-2 w-2 rounded-full bg-emerald-500"></span>
              Live Synced
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="mx-auto max-w-7xl p-6">
        {children}
      </main>
    </div>
  );
}
