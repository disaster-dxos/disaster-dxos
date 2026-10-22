// SPDX-License-Identifier: Apache-2.0
// Mọi trang cần đăng nhập, trừ trang gọi lại OIDC và các trang công khai (vd /minh-bach, #63).
const CONG_KHAI = ['/auth/', '/minh-bach']

export default defineNuxtRouteMiddleware(async (to) => {
  if (CONG_KHAI.some((p) => to.path.startsWith(p))) return
  const { khoiPhuc, urlDangNhap } = useAuth()
  if (await khoiPhuc()) return
  return navigateTo(await urlDangNhap(to.fullPath), { external: true, replace: true })
})
