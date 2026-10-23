// SPDX-License-Identifier: Apache-2.0
// Tin kêu cứu thời gian thực cho bản đồ (#60): GraphQL subscription của Hasura qua API Gateway
// (WebSocket ws(s)://<gateway>/graphql, giao thức graphql-transport-ws, thư viện graphql-ws).
// JWT Keycloak của người dùng nằm trong connection_init ({headers: {Authorization}}), vì trình duyệt
// không gửi được header khi mở WebSocket; Hasura kiểm chữ ký, hạn và áp quyền theo vai như với HTTP.
// Kết nối ổn định:
//  - mất mạng, gateway/Hasura khởi động lại → graphql-ws tự kết nối lại (backoff 0,5 → 20 s) và đăng ký lại;
//  - token được làm mới (useAuth tự làm 60 s trước hạn) → kết nối lại ngay bằng token mới;
//  - Hasura cắt kết nối đúng lúc JWT hết hạn (không có close frame, như mất mạng) → nối lại, connectionParams
//    tự làm mới token hết hạn;
//  - Hasura từ chối JWT/vai (đóng 4403) → làm mới token rồi kết nối lại một lần; vẫn bị từ chối thì dừng và
//    báo không có quyền; không làm mới được → hết phiên;
//  - trạng thái kết nối hiển thị cho người dùng (ô trạng thái + băng "mất kết nối" trên bản đồ).
import { createClient, type Client } from 'graphql-ws'
import { capNhatTinMoi, sapXepTin, type ChiTietTin, type TinKeuCuu } from '~/utils/tin'
import {
  SO_TIN_TOI_DA, SUB_BAN_DO, chiTietTuKetQua, choKetNoiLai, httpGraphqlUrl, phanLoaiDong, queryChiTiet,
  tinTuKetQua, wsGraphqlUrl,
} from '~/utils/tin-graphql'

export type TrangThaiBanDo = 'tat' | 'dang-ket-noi' | 'da-ket-noi' | 'mat-ket-noi' | 'het-phien' | 'loi'

let client: Client | null = null
let huySub: (() => void) | null = null
/** Mỗi lần tạo client mới tăng lên: bỏ qua sự kiện muộn của client cũ đã hủy */
let theHe = 0
let henGio: ReturnType<typeof setTimeout> | undefined
let henDonTinMoi: ReturnType<typeof setInterval> | undefined
let lanThu = 0
/** Số lần liên tiếp bị từ chối (4403) kể từ lần kết nối được gần nhất */
let lanTuChoi = 0
let daBiet = new Set<string>()
let lanDau = true
let dungWatch: (() => void) | undefined

export function useTinKeuCuu() {
  const rc = useRuntimeConfig().public
  const { session, user, khoiPhuc, lamMoi } = useAuth()
  const ds = useState<TinKeuCuu[]>('tin-ds', () => [])
  const moi = useState<Map<string, number>>('tin-moi', () => new Map())
  const trangThai = useState<TrangThaiBanDo>('tin-ket-noi', () => 'tat')
  const loi = useState<string>('tin-loi', () => '')
  const capNhatLuc = useState<number | null>('tin-cap-nhat', () => null)

  /** Vai gửi kèm X-Hasura-Role: điều phối nếu có, không thì vai mặc định trong token. */
  function vai(): string | undefined {
    const u = user.value
    if (!u) return undefined
    if (u.roles.includes('dieu-phoi')) return 'dieu-phoi'
    return u.defaultRole && u.roles.includes(u.defaultRole) ? u.defaultRole : u.roles[0]
  }

  async function headers(): Promise<Record<string, string>> {
    if (!(await khoiPhuc()) || !session.value) throw new Error('het-phien')
    const h: Record<string, string> = { Authorization: `Bearer ${session.value.accessToken}` }
    const v = vai()
    if (v) h['X-Hasura-Role'] = v
    return h
  }

  function nhanKetQua(data: unknown) {
    const moiNhat = tinTuKetQua(data)
    const kq = capNhatTinMoi(daBiet, moi.value, moiNhat, lanDau)
    daBiet = kq.daBiet
    lanDau = false
    moi.value = kq.moi
    ds.value = sapXepTin(moiNhat)
    capNhatLuc.value = Date.now()
  }

  function huyClient() {
    theHe++
    huySub?.()
    huySub = null
    void client?.dispose()
    client = null
  }

  /** Lỗi/đóng không tự hồi phục được trong graphql-ws (4400, 4401, lỗi GraphQL…): tự quyết định thử lại. */
  async function xuLyLoi(e: unknown, the: number) {
    if (the !== theHe) return
    const ev = e as { code?: number; reason?: string; message?: string } | Array<{ message?: string }>
    const lyDo = Array.isArray(ev) ? ev.map((x) => x.message ?? '').join('; ') : (ev?.reason || ev?.message || '')
    const code = Array.isArray(ev) ? undefined : ev?.code
    huyClient()
    if (lyDo === 'het-phien' || trangThai.value === 'het-phien') {
      trangThai.value = 'het-phien'
      return
    }
    const loai = phanLoaiDong(code, lyDo)
    if (loai === 'tu-choi' && ++lanTuChoi > 1) {
      // Token mới vẫn bị từ chối: thiếu quyền, không phải hết hạn. Không thử lại vòng vô hạn
      trangThai.value = 'loi'
      loi.value = 'Máy chủ từ chối kết nối: tài khoản không có quyền xem tin kêu cứu.'
      return
    }
    if (loai !== 'mang' && !(await lamMoi())) {
      trangThai.value = 'het-phien'
      loi.value = 'Phiên đăng nhập đã hết, hãy đăng nhập lại.'
      return
    }
    // Lỗi GraphQL (vd thiếu quyền) không phải lỗi mạng: báo rõ, vẫn thử lại thưa dần
    if (Array.isArray(ev)) {
      trangThai.value = 'loi'
      loi.value = `Máy chủ từ chối truy vấn: ${lyDo}`
    } else {
      trangThai.value = 'mat-ket-noi'
    }
    henGio = setTimeout(ketNoi, choKetNoiLai(lanThu++))
  }

  /** Tạo client mới. Không hạ trạng thái 'da-ket-noi': kết nối lại vì token mới thì người dùng không thấy gián đoạn. */
  function ketNoi() {
    clearTimeout(henGio)
    huyClient()
    const the = theHe
    if (trangThai.value === 'tat' || trangThai.value === 'het-phien') trangThai.value = 'dang-ket-noi'
    const c = createClient({
      url: wsGraphqlUrl(rc.gatewayUrl as string),
      lazy: false,
      connectionParams: async () => ({ headers: await headers() }),
      // Ping mỗi 20 giây: giữ kết nối qua APISIX (timeout đọc 60 giây) và phát hiện mạng chết
      keepAlive: 20_000,
      retryAttempts: Number.POSITIVE_INFINITY,
      retryWait: async (n) => { await new Promise((r) => setTimeout(r, choKetNoiLai(n))) },
      // 4403 (Hasura từ chối JWT/vai): thử lại cùng token là vô ích → để xuLyLoi làm mới token trước
      shouldRetry: (e) => (e as { code?: number } | null)?.code !== 4403,
      onNonLazyError: (e) => { void xuLyLoi(e, the) },
    })
    c.on('connected', () => {
      if (the !== theHe) return
      trangThai.value = 'da-ket-noi'
      loi.value = ''
      lanThu = 0
      lanTuChoi = 0
    })
    c.on('closed', () => {
      if (the === theHe && trangThai.value === 'da-ket-noi') trangThai.value = 'mat-ket-noi'
    })
    huySub = c.subscribe(
      { query: SUB_BAN_DO, variables: { gioiHan: SO_TIN_TOI_DA } },
      {
        next: (r) => {
          if (the !== theHe) return
          if (r.errors?.length) {
            void xuLyLoi(r.errors, the)
            return
          }
          nhanKetQua(r.data)
        },
        error: (e) => { void xuLyLoi(e, the) },
        complete: () => {
          // Hasura chỉ kết thúc subscription khi lỗi hoặc đóng kết nối: đăng ký lại
          if (the === theHe) void xuLyLoi({ code: 1000, reason: 'complete' }, the)
        },
      },
    )
    client = c
  }

  function batDau() {
    if (client) return
    lanDau = ds.value.length === 0
    ketNoi()
    // Token đổi (làm mới định kỳ) → kết nối lại ngay bằng token mới, không báo "mất kết nối"
    dungWatch = watch(() => session.value?.accessToken, (moiTok: string | undefined, cu: string | undefined) => {
      if (!moiTok) {
        huyClient()
        trangThai.value = 'het-phien'
      } else if (cu && moiTok !== cu && client) {
        ketNoi()
      }
    })
    // Bỏ cờ "tin mới" sau 60 giây kể cả khi không có kết quả mới
    henDonTinMoi = setInterval(() => {
      if (moi.value.size === 0) return
      const kq = capNhatTinMoi(daBiet, moi.value, ds.value, false)
      if (kq.moi.size !== moi.value.size) moi.value = kq.moi
    }, 5_000)
  }

  function dung() {
    clearTimeout(henGio)
    clearInterval(henDonTinMoi)
    dungWatch?.()
    dungWatch = undefined
    huyClient()
    trangThai.value = 'tat'
  }

  /** Thử kết nối lại ngay (nút "Thử lại" khi mất kết nối). */
  function thuLai() {
    lanThu = 0
    lanTuChoi = 0
    ketNoi()
  }

  /** Chi tiết một tin (query HTTP qua gateway, cột theo quyền của vai). */
  async function layChiTiet(id: string): Promise<ChiTietTin | null> {
    const r = await fetch(httpGraphqlUrl(rc.gatewayUrl as string), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(await headers()) },
      body: JSON.stringify({ query: queryChiTiet(vai()), variables: { id } }),
      cache: 'no-store',
    })
    if (!r.ok) throw new Error(`Không tải được chi tiết (HTTP ${r.status})`)
    const body = (await r.json()) as { data?: unknown; errors?: Array<{ message?: string }> }
    if (body.errors?.length) throw new Error(body.errors[0]?.message ?? 'Lỗi GraphQL')
    return chiTietTuKetQua(body.data)
  }

  return { ds, moi, trangThai, loi, capNhatLuc, batDau, dung, thuLai, layChiTiet, vai }
}
