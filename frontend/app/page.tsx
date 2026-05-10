"use client";

import { usePatients } from "@/hooks/usePatients";
import { usePatientDetail } from "@/hooks/usePatientDetail";
import DashboardShell from "@/components/layout/DashboardShell";
import SummaryCards from "@/components/summary/SummaryCards";
import FilterBar from "@/components/worklist/FilterBar";
import PatientWorklist, { PatientWorklistSkeleton } from "@/components/worklist/PatientWorklist";
import PatientDetailPanel from "@/components/detail/PatientDetailPanel";
import CohortDistribution from "@/components/summary/CohortDistribution";
import ConversionFunnel from "@/components/summary/ConversionFunnel";
import { useState, useMemo } from "react";

export default function DashboardPage() {
  const { data, isLoading, error } = usePatients();
  const { isPanelOpen } = usePatientDetail();
  
  // Filtering state
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedRisk, setSelectedRisk] = useState<string>("all");
  const [selectedCohort, setSelectedCohort] = useState<string>("all");
  
  const filteredPatients = useMemo(() => {
    const patients = data?.patients || [];
    return patients.filter((p) => {
      const matchesSearch = (p.patient_name || "").toLowerCase().includes(searchQuery.toLowerCase()) || 
                            (p.patient_id || "").toLowerCase().includes(searchQuery.toLowerCase());
      const matchesRisk = selectedRisk === "all" || p.risk_level === selectedRisk;
      const matchesCohort = selectedCohort === "all" || p.cohort_bucket === selectedCohort;
      return matchesSearch && matchesRisk && matchesCohort;
    });
  }, [data?.patients, searchQuery, selectedRisk, selectedCohort]);

  const availableCohorts = useMemo(() => {
    return data?.summary?.cohort_distribution ? Object.keys(data.summary.cohort_distribution).sort() : [];
  }, [data?.summary?.cohort_distribution]);

  return (
    <DashboardShell>
      {isLoading ? (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="glass-card rounded-xl p-6 h-[120px] animate-pulse bg-slate-50"></div>
            ))}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
             <div className="glass-card rounded-xl p-6 h-[300px] animate-pulse bg-slate-50"></div>
             <div className="glass-card rounded-xl p-6 h-[300px] animate-pulse bg-slate-50"></div>
          </div>
          <div className="glass-card rounded-xl overflow-hidden">
             <div className="p-4 border-b border-slate-100 flex gap-4">
               <div className="h-10 w-64 bg-slate-100 rounded-lg animate-pulse" />
               <div className="h-10 w-32 bg-slate-100 rounded-lg animate-pulse" />
               <div className="h-10 w-32 bg-slate-100 rounded-lg animate-pulse" />
             </div>
             <PatientWorklistSkeleton />
          </div>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
          Error loading patient data. Please ensure the backend is running.
        </div>
      ) : (
        <div className="space-y-6">
          {data?.summary && (
            <>
              <SummaryCards summary={data.summary} />
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="glass-card rounded-xl p-6">
                  <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">Cohort Distribution</h3>
                  <CohortDistribution summary={data.summary} />
                </div>
                <div className="glass-card rounded-xl p-6">
                  <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">Conversion Funnel</h3>
                  <ConversionFunnel summary={data.summary} />
                </div>
              </div>
            </>
          )}
          
          <div className="glass-card rounded-xl overflow-hidden">
            <FilterBar 
              searchQuery={searchQuery}
              setSearchQuery={setSearchQuery}
              selectedRisk={selectedRisk}
              setSelectedRisk={setSelectedRisk}
              selectedCohort={selectedCohort}
              setSelectedCohort={setSelectedCohort}
              availableCohorts={availableCohorts}
            />
            <PatientWorklist patients={filteredPatients} />
          </div>
        </div>
      )}
      
      {isPanelOpen && <PatientDetailPanel />}
    </DashboardShell>
  );
}
