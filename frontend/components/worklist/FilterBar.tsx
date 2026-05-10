import React from "react";
import { Search, SlidersHorizontal, X } from "lucide-react";

interface FilterBarProps {
  searchQuery: string;
  setSearchQuery: (val: string) => void;
  selectedRisk: string;
  setSelectedRisk: (val: string) => void;
  selectedCohort: string;
  setSelectedCohort: (val: string) => void;
  availableCohorts?: string[];
}

export default function FilterBar({
  searchQuery, setSearchQuery,
  selectedRisk, setSelectedRisk,
  selectedCohort, setSelectedCohort,
  availableCohorts = []
}: FilterBarProps) {
  
  const hasFilters = searchQuery !== "" || selectedRisk !== "all" || selectedCohort !== "all";

  const clearFilters = () => {
    setSearchQuery("");
    setSelectedRisk("all");
    setSelectedCohort("all");
  };

  return (
    <div className="border-b border-[var(--color-border)] bg-white p-4">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        {/* Search */}
        <div className="relative w-full md:w-80">
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
            <Search size={16} className="text-slate-400" />
          </div>
          <input
            type="text"
            className="block w-full rounded-md border-0 py-2 pl-10 pr-3 text-sm text-slate-900 ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-primary sm:text-sm sm:leading-6 bg-slate-50"
            placeholder="Search patients..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 text-sm font-medium text-slate-600">
            <SlidersHorizontal size={16} />
            Filters:
          </div>

          <select
            value={selectedRisk}
            onChange={(e) => setSelectedRisk(e.target.value)}
            className="rounded-md border-0 py-1.5 pl-3 pr-8 text-sm text-slate-900 ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-primary bg-slate-50 cursor-pointer"
          >
            <option value="all">All Risks</option>
            <option value="high">High Risk</option>
            <option value="medium">Medium Risk</option>
            <option value="low">Low Risk</option>
          </select>

          <select
            value={selectedCohort}
            onChange={(e) => setSelectedCohort(e.target.value)}
            className="rounded-md border-0 py-1.5 pl-3 pr-8 text-sm text-slate-900 ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-primary bg-slate-50 cursor-pointer max-w-[200px] truncate"
          >
            <option value="all">All Cohorts</option>
            {availableCohorts.map(cohort => (
              <option key={cohort} value={cohort}>{cohort}</option>
            ))}
          </select>

          {hasFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 rounded-md px-2 py-1.5 text-sm font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-colors"
            >
              <X size={14} />
              Clear
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
