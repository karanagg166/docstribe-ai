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

const RISK_ORDER: Record<string, number> = { HIGH: 0, MEDIUM: 1, LOW: 2 };

/** Sort patients by risk (HIGH → MEDIUM → LOW) and assign sequential ranks. */
function sortAndRank(patients: PatientInsight[]): PatientInsight[] {
  const sorted = [...patients].sort(
    (a, b) => (RISK_ORDER[a.risk_level] ?? 1) - (RISK_ORDER[b.risk_level] ?? 1)
  );
  return sorted.map((p, i) => ({ ...p, suggested_priority_rank: i + 1 }));
}

/**
 * Hook that connects to the SSE streaming endpoint and progressively
 * builds the dashboard state as each patient analysis completes.
 *
 * Uses `/api/dashboard/stream` — a same-origin Next.js route that proxies
 * the backend SSE. This works on both local and Vercel deployments without
 * any extra env vars or CORS configuration.
 *
 * Falls back to the batch `/api/dashboard` endpoint if SSE fails.
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

  /** Fallback: regular fetch from the batch endpoint. */
  const fetchBatch = useCallback(async () => {
    try {
      const res = await fetch('/api/dashboard');
      if (!res.ok) throw new Error(`Dashboard API returned ${res.status}`);
      const data = await res.json();

      const ranked = sortAndRank(data.patients ?? []);

      setState({
        patients: ranked,
        summary: data.summary ?? null,
        isLoading: false,
        isStreaming: false,
        error: null,
        progress: { current: ranked.length, total: ranked.length },
      });
    } catch (e) {
      setState(prev => ({
        ...prev,
        isLoading: false,
        isStreaming: false,
        error: e instanceof Error ? e : new Error('Failed to load dashboard'),
      }));
    }
  }, []);

  const connect = useCallback(() => {
    // Prevent double-connect in React StrictMode
    if (hasConnected.current) return;
    hasConnected.current = true;

    // Always use the same-origin streaming proxy route.
    // This works on both local (Docker) and Vercel deployments.
    const url = '/api/dashboard/stream';

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

    // Timeout: if no patient event within 20s, close SSE and fall back.
    let timeout = setTimeout(() => {
      console.warn('[streaming] No patient received within 20s, falling back to batch.');
      es.close();
      hasConnected.current = false;
      fetchBatch();
    }, 20000);

    es.addEventListener('patient', (event) => {
      clearTimeout(timeout);
      try {
        const data = JSON.parse(event.data);
        setState(prev => {
          const updated = [...prev.patients, data.patient as PatientInsight];
          const ranked = sortAndRank(updated);
          return {
            ...prev,
            patients: ranked,
            progress: { current: updated.length, total: data.total },
            isLoading: false,
          };
        });
      } catch (e) {
        console.error('Failed to parse patient event:', e);
      }
    });

    es.addEventListener('summary', (event) => {
      clearTimeout(timeout);
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
      clearTimeout(timeout);
      setState(prev => ({
        ...prev,
        isStreaming: false,
        isLoading: false,
      }));
      es.close();
    });

    es.onerror = () => {
      clearTimeout(timeout);
      console.warn('[streaming] EventSource error, falling back to batch.');
      es.close();
      // Only fall back if we haven't received any patients yet
      if (state.patients.length === 0) {
        hasConnected.current = false;
        fetchBatch();
      } else {
        // We already have some patients, just mark streaming as done
        setState(prev => ({ ...prev, isStreaming: false, isLoading: false }));
      }
    };
  }, [fetchBatch]);

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
