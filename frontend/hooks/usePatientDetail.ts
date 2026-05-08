import { create } from 'zustand';
import { PatientInsight } from '../types/patient';

interface PatientDetailState {
  selectedPatient: PatientInsight | null;
  isPanelOpen: boolean;
  openPanel: (patient: PatientInsight) => void;
  closePanel: () => void;
}

export const usePatientDetail = create<PatientDetailState>((set) => ({
  selectedPatient: null,
  isPanelOpen: false,
  openPanel: (patient) => set({ selectedPatient: patient, isPanelOpen: true }),
  closePanel: () => set({ selectedPatient: null, isPanelOpen: false }),
}));
