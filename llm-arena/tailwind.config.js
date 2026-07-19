/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#fff5f1',
          100: '#ffe6db',
          200: '#ffc7b0',
          300: '#ff9f7a',
          400: '#ff7a55',
          500: '#ff5c33',
          600: '#e84a22',
          700: '#c03a18',
          800: '#9a3218',
          900: '#7c2d18',
        },
        surface: {
          0: '#ffffff',
          50: '#f3efe6',
          100: '#e8e2d6',
          200: '#d4cdc0',
          300: '#b8b0a2',
          400: '#9a9488',
          500: '#7a7368',
          600: '#5c564c',
          700: '#3d3832',
          800: '#24201b',
          900: '#12100e',
          950: '#0a0908',
        },
        accent: {
          cyan: '#3dd6c6',
          emerald: '#3dd6c6',
          amber: '#e8c547',
          rose: '#ff4d6d',
          violet: '#c4a1ff',
          signal: '#ff5c33',
        },
        // Bridge: existing kimi-* classes → Colosseum Protocol
        kimi: {
          dark: '#0a0908',
          card: '#12100e',
          surface: '#1a1714',
          'surface-hover': '#24201b',
          border: 'rgba(243, 239, 230, 0.08)',
          'border-hover': 'rgba(243, 239, 230, 0.14)',
          text: '#f3efe6',
          muted: '#7a7368',
        },
      },
      fontFamily: {
        sans: ['"Source Serif 4"', 'Georgia', 'serif'],
        display: ['Syne', 'system-ui', 'sans-serif'],
        body: ['"Source Serif 4"', 'Georgia', 'serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        xl: '14px',
        '2xl': '14px',
      },
      boxShadow: {
        duel: '0 18px 40px -20px rgba(255, 92, 51, 0.35)',
        stage: '0 24px 60px -28px rgba(0, 0, 0, 0.8)',
      },
      animation: {
        'gradient-x': 'gradient-x 15s ease infinite',
        float: 'float 6s ease-in-out infinite',
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        glow: 'glow 2.4s ease-in-out infinite alternate',
        'slide-up': 'slide-up 0.55s cubic-bezier(0.22, 1, 0.36, 1)',
        'fade-in': 'fade-in 0.4s ease-out',
        'scale-in': 'scale-in 0.35s cubic-bezier(0.22, 1, 0.36, 1)',
        marquee: 'marquee 28s linear infinite',
      },
      keyframes: {
        'gradient-x': {
          '0%, 100%': { 'background-size': '200% 200%', 'background-position': 'left center' },
          '50%': { 'background-size': '200% 200%', 'background-position': 'right center' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-14px)' },
        },
        glow: {
          '0%': { boxShadow: '0 0 18px rgba(255, 92, 51, 0.12)' },
          '100%': { boxShadow: '0 0 36px rgba(255, 92, 51, 0.32)' },
        },
        'slide-up': {
          '0%': { transform: 'translateY(22px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'scale-in': {
          '0%': { transform: 'scale(0.96)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        marquee: {
          from: { transform: 'translateX(0)' },
          to: { transform: 'translateX(-50%)' },
        },
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [
    function ({ addUtilities }) {
      addUtilities({
        '.text-gradient': {
          background: 'linear-gradient(115deg, #fff6ee 10%, #ff8a66 42%, #ff5c33 68%, #e8c547 100%)',
          '-webkit-background-clip': 'text',
          '-webkit-text-fill-color': 'transparent',
          'background-clip': 'text',
        },
        '.bg-glass': {
          background: 'rgba(18, 16, 14, 0.78)',
          'backdrop-filter': 'blur(18px)',
          '-webkit-backdrop-filter': 'blur(18px)',
        },
        '.border-glow': {
          border: '1px solid rgba(255, 92, 51, 0.28)',
          'box-shadow': '0 0 24px rgba(255, 92, 51, 0.12), inset 0 0 20px rgba(255, 92, 51, 0.04)',
        },
      })
    },
  ],
}
