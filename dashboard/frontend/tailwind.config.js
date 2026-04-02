/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        bg: '#0a0a0d',
        card: '#111116',
        border: '#222228',
        text: '#e0e0d8',
        subtext: '#888880',
        accent: '#c8a84e',
        'accent-dim': '#8a7236',
        success: '#3a7d5c',
        warning: '#c8a84e',
        error: '#bf3a3a',
        info: '#4a5abf',
        'card-hover': '#18181f',
      },
      fontFamily: {
        sans: ['Pretendard', 'Apple SD Gothic Neo', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
      borderColor: {
        DEFAULT: '#222228',
      },
    },
  },
  plugins: [],
}
