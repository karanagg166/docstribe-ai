import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { usePatientDetail } from "@/hooks/usePatientDetail";
import { X, Calendar, Activity, Info, PhoneForwarded } from "lucide-react";
import { getRiskBgClass, getCohortColorClass } from "@/lib/utils";
import SourceTraceBadge from "./SourceTraceBadge";

export default function PatientDetailPanel() {
  const { selectedPatient, isPanelOpen, closePanel } = usePatientDetail();
  const [activeTab, setActiveTab] = useState("summary");

  if (!selectedPatient) return null;

  return (
    <AnimatePresence>
      {isPanelOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closePanel}
            className="fixed inset-0 z-40 bg-slate-900/20 backdrop-blur-sm"
          />

          {/* Panel */}
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", bounce: 0, duration: 0.4 }}
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col bg-white shadow-2xl sm:border-l sm:border-slate-200"
          >
            {/* Header */}
            <div className="flex items-start justify-between border-b border-slate-200 bg-slate-50 px-6 py-5">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-xl font-semibold text-slate-900">{selectedPatient.patient_name}</h2>
                  <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium capitalize ${getRiskBgClass(selectedPatient.risk_level)}`}>
                    {selectedPatient.risk_level} Risk
                  </span>
                </div>
                <div className="mt-1 flex items-center gap-2 text-sm text-slate-500">
                  <span>{selectedPatient.patient_id}</span>
                  <span>•</span>
                  <span>{selectedPatient.age}y {selectedPatient.gender}</span>
                  <span>•</span>
                  <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-medium ${getCohortColorClass(selectedPatient.cohort_bucket)}`}>
                    {selectedPatient.cohort_bucket}
                  </span>
                </div>
              </div>
              <button
                onClick={closePanel}
                className="rounded-full p-2 text-slate-400 hover:bg-slate-200 hover:text-slate-600 transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-slate-200 px-6">
              {[
                { id: "summary", label: "Summary" },
                { id: "timeline", label: "Visit Timeline" },
                { id: "risks", label: "Risk Flags" },
                { id: "actions", label: "Next Actions" },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
                    activeTab === tab.id
                      ? "border-primary text-primary"
                      : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto p-6 hide-scrollbar">
              {activeTab === "summary" && (
                <div className="space-y-6">
                  {/* Clinical Summary */}
                  <section>
                    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-2">
                      <Info size={16} /> Clinical Summary
                    </h3>
                    <div className="rounded-lg bg-slate-50 p-4 text-sm leading-relaxed text-slate-700">
                      {selectedPatient.clinical_summary}
                    </div>
                  </section>
                  
                  {/* Risk Reasoning */}
                  <section>
                    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-2">
                      <Activity size={16} /> Risk Reasoning
                    </h3>
                    <div className={`rounded-lg border p-4 text-sm leading-relaxed ${
                      selectedPatient.risk_level === 'high' ? 'bg-rose-50 border-rose-100 text-rose-800' : 
                      selectedPatient.risk_level === 'medium' ? 'bg-amber-50 border-amber-100 text-amber-800' :
                      'bg-emerald-50 border-emerald-100 text-emerald-800'
                    }`}>
                      {selectedPatient.risk_reasoning}
                    </div>
                  </section>
                  
                  {/* Conversion Status */}
                  <section>
                    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-2">
                      <PhoneForwarded size={16} /> Conversion Status
                    </h3>
                    <div className="rounded-lg border border-slate-200 p-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="text-xs text-slate-500">Status</div>
                          <div className="font-medium text-slate-900 mt-1">{selectedPatient.conversion_status.admission_status}</div>
                        </div>
                        {selectedPatient.conversion_status.barrier && (
                          <div>
                            <div className="text-xs text-slate-500">Barrier</div>
                            <div className="font-medium text-amber-700 mt-1">{selectedPatient.conversion_status.barrier}</div>
                          </div>
                        )}
                        {selectedPatient.conversion_status.barrier_detail && (
                          <div className="col-span-2 mt-2 text-sm text-slate-600">
                            {selectedPatient.conversion_status.barrier_detail}
                          </div>
                        )}
                      </div>
                    </div>
                  </section>
                </div>
              )}

              {activeTab === "risks" && (
                <div className="space-y-4">
                  {selectedPatient.risk_flags.length === 0 ? (
                    <div className="text-sm text-slate-500 italic">No significant risk flags detected.</div>
                  ) : (
                    selectedPatient.risk_flags.map((flag, idx) => (
                      <div key={idx} className={`rounded-lg border p-4 ${
                        flag.severity === 'high' ? 'bg-rose-50 border-rose-100' : 
                        flag.severity === 'medium' ? 'bg-amber-50 border-amber-100' :
                        'bg-emerald-50 border-emerald-100'
                      }`}>
                        <div className="flex justify-between items-start mb-2">
                          <h4 className="font-medium text-slate-900">{flag.flag}</h4>
                          <SourceTraceBadge trace={flag.source} />
                        </div>
                        <p className="text-sm text-slate-700">{flag.detail}</p>
                      </div>
                    ))
                  )}
                  
                  {selectedPatient.care_path_variance.detected && (
                    <div className="mt-8">
                      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-500">Care Path Variances</h3>
                      <div className="space-y-3">
                        {selectedPatient.care_path_variance.variances.map((variance, idx) => (
                          <div key={idx} className="rounded-lg border border-indigo-100 bg-indigo-50 p-4">
                            <h4 className="font-medium text-indigo-900 mb-2">{variance.description}</h4>
                            <div className="text-sm text-indigo-800">
                              <span className="font-semibold">Expected:</span> {variance.expected_action}
                            </div>
                            <div className="text-sm text-indigo-800 mt-1">
                              <span className="font-semibold">Actual:</span> {variance.actual_finding}
                            </div>
                            <div className="mt-3 flex gap-2">
                              {variance.source.map((src, i) => (
                                <SourceTraceBadge key={i} trace={src} />
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {activeTab === "actions" && (
                <div className="space-y-4">
                  {selectedPatient.next_actions.map((action, idx) => (
                    <div key={idx} className="flex gap-4 rounded-lg border border-slate-200 p-4">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-sm font-bold text-slate-600">
                        {action.priority}
                      </div>
                      <div className="flex-1">
                        <div className="flex justify-between items-start">
                          <h4 className="font-medium text-slate-900">{action.action}</h4>
                          <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded capitalize">
                            {action.action_type.replace('_', ' ')}
                          </span>
                        </div>
                        <p className="mt-1 text-sm text-slate-600">{action.reason}</p>
                        <div className="mt-3">
                          <SourceTraceBadge trace={action.source} />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {activeTab === "timeline" && (
                <div className="relative pl-4 before:absolute before:inset-y-0 before:left-[15px] before:w-0.5 before:bg-slate-200">
                  {selectedPatient.visit_timeline.map((visit, idx) => (
                    <div key={idx} className="relative mb-8 pl-6 last:mb-0">
                      <div className="absolute left-[-5px] top-1 h-3 w-3 rounded-full bg-primary ring-4 ring-white" />
                      <div className="mb-1 flex items-center gap-2">
                        <span className="text-sm font-bold text-slate-900">Visit {visit.visit_number}</span>
                        <span className="text-xs text-slate-500"><Calendar size={12} className="inline mr-1"/>{visit.date}</span>
                      </div>
                      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                        <div className="mb-2">
                          <span className="text-xs font-semibold text-slate-500 uppercase">Chief Complaint</span>
                          <p className="text-sm text-slate-800">{visit.chief_complaint}</p>
                        </div>
                        {visit.doctor_note && (
                          <div className="mb-2">
                            <span className="text-xs font-semibold text-slate-500 uppercase">Note</span>
                            <p className="text-sm text-slate-700 italic border-l-2 border-slate-200 pl-2 mt-1">{visit.doctor_note}</p>
                          </div>
                        )}
                        <div className="flex gap-6 mt-4">
                          {visit.labs_ordered.length > 0 && (
                            <div>
                              <span className="text-xs font-semibold text-slate-500 uppercase block mb-1">Labs Ordered</span>
                              <ul className="list-disc pl-4 text-xs text-slate-700">
                                {visit.labs_ordered.map((lab, i) => <li key={i}>{lab}</li>)}
                              </ul>
                            </div>
                          )}
                          {visit.medications_prescribed.length > 0 && (
                            <div>
                              <span className="text-xs font-semibold text-slate-500 uppercase block mb-1">Medications</span>
                              <ul className="list-disc pl-4 text-xs text-slate-700">
                                {visit.medications_prescribed.map((med, i) => <li key={i}>{med}</li>)}
                              </ul>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
