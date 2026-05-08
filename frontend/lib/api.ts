import axios from 'axios';
import { DashboardResponse, PatientInsight } from '../types/patient';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || '/api',
});

export const fetchDashboard = async (): Promise<DashboardResponse> => {
  const response = await api.get('/dashboard');
  return response.data;
};

export const analyzePatient = async (patientId: string): Promise<PatientInsight> => {
  const response = await api.post(`/analyze/${patientId}`);
  return response.data;
};
