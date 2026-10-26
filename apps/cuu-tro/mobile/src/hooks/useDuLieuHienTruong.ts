// SPDX-License-Identifier: Apache-2.0
// Dữ liệu đọc của màn Hiện trường qua TanStack Query: tin mình gửi (tình nguyện viên) hoặc tin của đội
// (cứu hộ), và đội của mình (cứu hộ). Mất mạng thì giữ dữ liệu đã tải.
import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/config/queryClient';
import { layDoiCuaToi, layTinCuaToi } from '@/services/graphql';
import { useAuthStore } from '@/stores/authStore';
import { vaiChinh } from '@/utils/jwt';

export function useVai() {
  return vaiChinh(useAuthStore(s => s.nguoiDung));
}

export function useTinCuaToi() {
  const vai = useVai();
  return useQuery({
    queryKey: queryKeys.tinCuaToi(vai ?? ''),
    // Hasura lọc theo vai: tinh-nguyen tin mình tạo, cuu-ho tin của đội, dieu-phoi mọi tin đang mở
    queryFn: () => layTinCuaToi(vai ?? 'tinh-nguyen'),
    enabled: vai !== null,
  });
}

export function useDoiCuaToi() {
  const vai = useVai();
  return useQuery({ queryKey: queryKeys.doiCuaToi(), queryFn: layDoiCuaToi, enabled: vai === 'cuu-ho' });
}
