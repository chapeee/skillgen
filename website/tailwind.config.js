/** @type {import('tailwindcss').Config} */
module.exports = {
  // Relative to this file, not the working directory, so builds started from the repo root
  // (`npm --prefix website ...`) still find every class.
  content: {
    relative: true,
    files: ['./src/**/*.{js,jsx,ts,tsx,md,mdx}', './docs/**/*.{md,mdx}'],
  },
  // Docusaurus ships Infima as its base layer. Tailwind's reset and `container`
  // would fight it inside the documentation, so both stay off.
  corePlugins: {
    preflight: false,
    container: false,
  },
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        ink: {
          950: '#020308',
          900: '#05070d',
          850: '#080b14',
          800: '#0b0f1b',
          700: '#111728',
          600: '#1a2238',
          500: '#27314d',
        },
        galaxy: {
          50: 'rgb(var(--sg-galaxy-50) / <alpha-value>)',
          100: 'rgb(var(--sg-galaxy-100) / <alpha-value>)',
          200: 'rgb(var(--sg-galaxy-200) / <alpha-value>)',
          300: 'rgb(var(--sg-galaxy-300) / <alpha-value>)',
          400: 'rgb(var(--sg-galaxy-400) / <alpha-value>)',
          500: 'rgb(var(--sg-galaxy-500) / <alpha-value>)',
          600: 'rgb(var(--sg-galaxy-600) / <alpha-value>)',
          700: 'rgb(var(--sg-galaxy-700) / <alpha-value>)',
          800: 'rgb(var(--sg-galaxy-800) / <alpha-value>)',
          900: 'rgb(var(--sg-galaxy-900) / <alpha-value>)',
          950: 'rgb(var(--sg-galaxy-950) / <alpha-value>)',
        },
        nebula: {
          300: 'rgb(var(--sg-nebula-300) / <alpha-value>)',
          400: 'rgb(var(--sg-nebula-400) / <alpha-value>)',
          500: 'rgb(var(--sg-nebula-500) / <alpha-value>)',
        },
        // "White" is the ink colour of the current surface: true white on the
        // dark showcases, dark ink on the white page, at any opacity.
        white: 'rgb(var(--sg-ink) / <alpha-value>)',
      },
      fontFamily: {
        sans: [
          '"Inter Variable"',
          'Inter',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          '"Segoe UI"',
          'sans-serif',
        ],
        mono: [
          '"Geist Mono Variable"',
          '"Geist Mono"',
          '"JetBrains Mono Variable"',
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Consolas',
          'monospace',
        ],
      },
      letterSpacing: {
        display: '-0.035em',
      },
      maxWidth: {
        shell: '76rem',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(14px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'flow-dash': {
          to: { strokeDashoffset: '-48' },
        },
        shimmer: {
          '0%': { backgroundPosition: '200% 0' },
          '100%': { backgroundPosition: '-200% 0' },
        },
        blink: {
          '0%, 49%': { opacity: '1' },
          '50%, 100%': { opacity: '0' },
        },
        orbit: {
          to: { transform: 'rotate(360deg)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.9s cubic-bezier(0.22, 1, 0.36, 1) both',
        'flow-dash': 'flow-dash 1.6s linear infinite',
        shimmer: 'shimmer 6s linear infinite',
        blink: 'blink 1.1s step-end infinite',
        orbit: 'orbit 40s linear infinite',
      },
    },
  },
  plugins: [],
};
