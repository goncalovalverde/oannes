/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg:        '#0d0f17',
        surface:   '#13161f',
        surface2:  '#1c2030',
        border:    '#252836',
        border2:   '#2f3347',
        primary:   '#6366f1',
        success:   '#22c55e',
        warning:   '#f59e0b',
        danger:    '#ef4444',
        text:      '#e2e8f0',
        muted:     '#64748b',
        muted2:    '#94a3b8',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
