import { useQuery } from '@tanstack/react-query';
import { fetchDashboard } from '../lib/api';

export function usePatients() {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
  });
}
