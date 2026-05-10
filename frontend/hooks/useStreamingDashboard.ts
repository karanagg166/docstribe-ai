import { useState, useEffect, useCallback, useRef } from 'react';
import { PatientInsight, DashboardSummary } from '../types/patient';

interface StreamingState {
  patients: PatientInsight[];
  summary: DashboardSummary | null;
  isLoading: boolean;
  isStreaming: boolean;
  error: Error | null;
  progress: { current: number; total: number };
}

/**
 * Hook that connects to the SSE streaming endpoint and progressively
 * builds the dashboard state as each patient analysis completes.
 *
 * - If the backend has cached data, all events arrive nearly instantly.
 * - If not cached, patients trickle in one-by-one as the LLM finishes each.
 * - The summary arrives after the last patient.
 */
export function useStreamingDashboard() {
  const [state, setState] = useState<StreamingState>({
    patients: [],
    summary: null,
    isLoading: true,
    isStreaming: false,
    error: null,
    progress: { current: 0, total: 0 },
  });

  const eventSourceRef = useRef<EventSource | null>(null);
  const hasConnected = useRef(false);

  const connect = useCallback(() => {
    // Prevent double-connect in React StrictMode
    if (hasConnected.current) return;
    hasConnected.current = true;

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || '/api';
    const url = `${apiUrl}/dashboard/stream`;

    setState(prev => ({
      ...prev,
      isLoading: true,
      isStreaming: true,
      patients: [],
      summary: null,
      error: null,
      progress: { current: 0, total: 0 },
    }));

    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.addEventListener('patient', (event) => {
      try {
        const data = JSON.parse(event.data);
        setState(prev => ({
          ...prev,
          patients: [...prev.patients, data.patient as PatientInsight],
          progress: { current: prev.patients.length + 1, total: data.total },
          isLoading: false, // content is available after the first patient
        }));
      } catch (e) {
        console.error('Failed to parse patient event:', e);
      }
    });

    es.addEventListener('summary', (event) => {
      try {
        const data = JSON.parse(event.data);
        setState(prev => ({
          ...prev,
          summary: data as DashboardSummary,
        }));
      } catch (e) {
        console.error('Failed to parse summary event:', e);
      }
    });

    es.addEventListener('complete', () => {
      setState(prev => ({
        ...prev,
        isStreaming: false,
        isLoading: false,
      }));
      es.close();
    });

    es.addEventListener('error', (event) => {
      // Check if it's a custom error event from the server
      const messageEvent = event as MessageEvent;
      if (messageEvent.data) {
        try {
          const errorData = JSON.parse(messageEvent.data);
          setState(prev => ({
            ...prev,
            isLoading: false,
            isStreaming: false,
            error: new Error(errorData.detail || 'Stream error'),
          }));
        } catch {
          setState(prev => ({
            ...prev,
            isLoading: false,
            isStreaming: false,
            error: new Error('Stream connection failed'),
          }));
        }
      } else {
        // EventSource connection error (network issue, etc.)
        setState(prev => ({
          ...prev,
          isLoading: prev.patients.length === 0, // only show loading if we have no data yet
          isStreaming: false,
          error: prev.patients.length === 0 ? new Error('Failed to connect to analysis stream') : null,
        }));
      }
      es.close();
    });
  }, []);

  useEffect(() => {
    connect();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [connect]);

  return {
    data: state.patients.length > 0 ? {
      patients: state.patients,
      summary: state.summary,
    } : undefined,
    isLoading: state.isLoading,
    isStreaming: state.isStreaming,
    error: state.error,
    progress: state.progress,
  };
}
