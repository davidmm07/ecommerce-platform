import { MutationCache, QueryClient } from '@tanstack/react-query';

import { isRetryable } from '@/shared/api/http';

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => isRetryable(error) && failureCount < 2,
      },
      mutations: {
        retry: false,
      },
    },
    mutationCache: new MutationCache(),
  });
}
