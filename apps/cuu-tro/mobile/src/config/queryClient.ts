// SPDX-License-Identifier: Apache-2.0
// TanStack Query: dữ liệu ĐỌC từ máy chủ (tin của tôi, đội của tôi). Dữ liệu GHI không đi qua đây mà qua hàng
// đợi offline (stores/hangDoiStore.ts) để không mất khi mất mạng.
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      // Mất mạng: giữ dữ liệu cũ trên màn hình, không báo lỗi liên tục
      networkMode: 'offlineFirst',
    },
  },
});

export const queryKeys = {
  tinCuaToi: (vai: string) => ['tin-cua-toi', vai] as const,
  doiCuaToi: () => ['doi-cua-toi'] as const,
};
