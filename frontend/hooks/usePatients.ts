import { useQuery } from '@tanstack/react-query';
import { fetchDashboard } from '../lib/api';

export function usePatients() {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
    retry: 1,                     // avoid flooding backend with retries
    staleTime: 5 * 60 * 1000,    // 5 min — data doesn't change often
    gcTime: 10 * 60 * 1000,      // keep in cache 10 min
  });
}
