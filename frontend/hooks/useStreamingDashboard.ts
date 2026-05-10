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
 * If SSE is unavailable (e.g. Vercel proxy doesn't support it), it
 * falls back to the regular batch /api/dashboard endpoint automatically.
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

    // SSE must connect directly to the backend — Next.js rewrites buffer
    // the response, which breaks streaming.  In production, use the public
    // backend URL; locally, the /api proxy works fine for dev.
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL;

    // If we don't have a direct backend URL, skip SSE entirely and use batch.
    if (!backendUrl) {
      fetchBatch();
      return;
    }

    const url = `${backendUrl}/dashboard/stream`;

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

    // Timeout: if no patient event within 15s, close SSE and fall back.
    const timeout = setTimeout(() => {
      es.close();
      hasConnected.current = false;
      fetchBatch();
    }, 15000);

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

    es.addEventListener('error', (event) => {
      clearTimeout(timeout);
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
          // SSE connection failed — fall back to batch
          es.close();
          hasConnected.current = false;
          fetchBatch();
          return;
        }
      } else {
        // EventSource connection error — fall back to batch
        es.close();
        hasConnected.current = false;
        fetchBatch();
        return;
      }
      es.close();
    });
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
