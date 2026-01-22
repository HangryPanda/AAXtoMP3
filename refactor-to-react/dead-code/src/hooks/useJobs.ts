import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/services/api';
import { Job, LogMessage } from '@/types/shared';
import { useEffect, useState } from 'react';

const fetchJobs = async (): Promise<Job[]> => {
  const { data } = await api.get('/jobs');
  return data;
};

const createJob = async (payload: { type: string, asins: string[] }): Promise<Job> => {
  const { data } = await api.post('/jobs', payload);
  return data;
};

const cancelJob = async (jobId: string): Promise<void> => {
  await api.post(`/jobs/${jobId}/cancel`);
};

export function useJobs() {
  return useQuery({
    queryKey: ['jobs'],
    queryFn: fetchJobs,
    refetchInterval: 5000, // Polling fallback if WS fails
  });
}

export function useCreateJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createJob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });
}

export function useCancelJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cancelJob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });
}

// WebSocket hook for logs
export function useJobSocket(jobId: string | null) {
  const [logs, setLogs] = useState<LogMessage[]>([]);
  
  useEffect(() => {
    if (!jobId) return;

    // Use standard WebSocket or a library like socket.io-client
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';
    const socket = new WebSocket(`${wsUrl}/ws/jobs/${jobId}`);

    socket.onmessage = (event) => {
      try {
        const message: LogMessage = JSON.parse(event.data);
        setLogs((prev) => [...prev, message]);
      } catch (e) {
        console.error('Failed to parse WS message', e);
      }
    };

    return () => {
      socket.close();
    };
  }, [jobId]);

  return logs;
}
