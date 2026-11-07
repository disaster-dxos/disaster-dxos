// SPDX-License-Identifier: Apache-2.0
// Theme Nuxt UI theo bộ nhận diện Team 1 (bảng màu khai báo trong assets/css/main.css).
export default defineAppConfig({
  ui: {
    colors: {
      primary: 'navy',
      secondary: 'cam',
      info: 'nuoc',
      success: 'ok',
      warning: 'cao',
      error: 'khan',
      neutral: 'slate',
    },
    button: {
      // Nút cam: chữ navy-950 (5,98:1) thay vì chữ trắng (2,78:1)
      compoundVariants: [
        { color: 'secondary', variant: 'solid', class: 'text-navy-950 font-semibold hover:bg-cam-600 active:bg-cam-600 disabled:bg-secondary aria-disabled:bg-secondary' },
      ],
    },
    card: {
      slots: {
        root: 'bg-elevated ring ring-default shadow-xs',
      },
    },
    dashboardNavbar: {
      slots: {
        root: 'h-14 border-b border-default bg-elevated/90 backdrop-blur px-4 sm:px-5',
        title: 'text-base sm:text-lg font-bold tracking-tight text-highlighted',
      },
    },
    badge: {
      compoundVariants: [
        { color: 'secondary', variant: 'solid', class: 'text-navy-950 font-semibold' },
      ],
    },
  },
})
