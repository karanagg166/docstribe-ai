"use client";

import { usePatients } from "@/hooks/usePatients";
import { usePatientDetail } from "@/hooks/usePatientDetail";
import DashboardShell from "@/components/layout/DashboardShell";
import SummaryCards from "@/components/summary/SummaryCards";
import FilterBar from "@/components/worklist/FilterBar";
import PatientWorklist from "@/components/worklist/PatientWorklist";
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

  return (
    <DashboardShell>
      {isLoading ? (
        <div className="flex h-64 items-center justify-center">
          <div className="flex flex-col items-center space-y-4">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
            <p className="text-sm text-text-muted animate-pulse">Analyzing clinical data...</p>
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
            />
            <PatientWorklist patients={filteredPatients} />
          </div>
        </div>
      )}
      
      {isPanelOpen && <PatientDetailPanel />}
    </DashboardShell>
  );
}
