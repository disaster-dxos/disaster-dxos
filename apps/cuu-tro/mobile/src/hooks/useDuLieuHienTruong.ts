// SPDX-License-Identifier: Apache-2.0
// Dữ liệu đọc của màn Hiện trường qua TanStack Query: tin mình gửi (tình nguyện viên) hoặc tin của đội
// (cứu hộ), và đội của mình (cứu hộ). Mất mạng thì giữ dữ liệu đã tải; mở lại app khi mất mạng thì nạp bản sao
// mã hóa trên máy (services/banSao.ts, #113) với đúng mốc thời gian tải, để màn hình báo "đã tải lúc …".
import { useQuery, useQueryClient, type QueryKey, type UseQueryResult } from '@tanstack/react-query';
import { useEffect } from 'react';
import { queryKeys } from '@/config/queryClient';
import { docBanSao, ghiBanSao } from '@/services/banSao';
import { layDoiCuaToi, layTinCuaToi } from '@/services/graphql';
import { useAuthStore } from '@/stores/authStore';
import { boQua } from '@/utils/boQua';
import { vaiChinh } from '@/utils/jwt';

export function useVai() {
  return vaiChinh(useAuthStore(s => s.nguoiDung));
}

/** Nạp bản sao vào cache khi cache còn trống; ghi bản sao sau mỗi lần tải thành công từ máy chủ */
function useBanSao<T>(q: UseQueryResult<T>, queryKey: QueryKey, ten: string, bat: boolean) {
  const qc = useQueryClient();
  const nguoiDung = useAuthStore(s => s.nguoiDung);
  const vai = vaiChinh(nguoiDung);
  const chu = nguoiDung && vai ? `${nguoiDung.sub}|${vai}` : null;
  const khoa = JSON.stringify(queryKey);

  useEffect(() => {
    if (!bat || !chu) {
      return;
    }
    let huy = false;
    boQua(
      docBanSao<T>(ten, chu).then(b => {
        if (!huy && b && qc.getQueryData(queryKey) === undefined) {
          qc.setQueryData(queryKey, b.duLieu, { updatedAt: b.luc });
        }
      }),
    );
    return () => {
      huy = true;
    };
    // queryKey thay bằng khoa (chuỗi) để không chạy lại mỗi lần render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bat, chu, ten, khoa, qc]);

  const { data, dataUpdatedAt, isFetchedAfterMount } = q;
  useEffect(() => {
    // Chỉ ghi dữ liệu vừa tải từ máy chủ, không ghi lại chính bản sao vừa nạp
    if (bat && chu && isFetchedAfterMount && data !== undefined && dataUpdatedAt > 0) {
      boQua(ghiBanSao(ten, chu, data, dataUpdatedAt));
    }
  }, [bat, chu, ten, data, dataUpdatedAt, isFetchedAfterMount]);
}

export function useTinCuaToi() {
  const vai = useVai();
  const queryKey = queryKeys.tinCuaToi(vai ?? '');
  const q = useQuery({
    queryKey,
    // Hasura lọc theo vai: tinh-nguyen tin mình tạo, cuu-ho tin của đội, dieu-phoi mọi tin đang mở
    queryFn: () => layTinCuaToi(vai ?? 'tinh-nguyen'),
    enabled: vai !== null,
  });
  useBanSao(q, queryKey, 'tin-cua-toi', vai !== null);
  return q;
}

export function useDoiCuaToi() {
  const vai = useVai();
  const queryKey = queryKeys.doiCuaToi();
  const q = useQuery({ queryKey, queryFn: layDoiCuaToi, enabled: vai === 'cuu-ho' });
  useBanSao(q, queryKey, 'doi-cua-toi', vai === 'cuu-ho');
  return q;
}
