import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/services/api';
import { Book } from '@/types/shared';

// Fetch all books
const fetchBooks = async (params?: any): Promise<Book[]> => {
  const { data } = await api.get('/library', { params });
  return data;
};

// Fetch single book
const fetchBook = async (asin: string): Promise<Book> => {
  const { data } = await api.get(`/library/${asin}`);
  return data;
};

// Sync library
const syncLibrary = async (): Promise<void> => {
  await api.post('/library/sync');
};

export function useBooks(params?: any) {
  return useQuery({
    queryKey: ['books', params],
    queryFn: () => fetchBooks(params),
  });
}

export function useBookDetails(asin: string) {
  return useQuery({
    queryKey: ['book', asin],
    queryFn: () => fetchBook(asin),
    enabled: !!asin,
  });
}

export function useSyncLibrary() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: syncLibrary,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['books'] });
    },
  });
}
