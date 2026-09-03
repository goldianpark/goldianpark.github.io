/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#fefdf8',
          100: '#fdf8ea',
          200: '#faeccb',
          300: '#f5dc9d',
          400: '#edc467',
          500: '#d9a738', // Golden Amber
          600: '#b8860b', // Dark Goldenrod (High contrast, AAA accessible)
          700: '#946608',
          800: '#7a510d',
          900: '#4a2f07',
        },
        gold: {
          50: '#fcfaf2',
          100: '#f8f2dc',
          200: '#efe3b5',
          300: '#e3cf86',
          400: '#d4b754',
          500: '#c5a034',
          600: '#aa8228',
          700: '#876222',
          800: '#6f4f21',
          900: '#5e431f',
        },
      },
      fontFamily: {
        sans: [
          'Pretendard',
          '-apple-system',
          'BlinkMacSystemFont',
          'system-ui',
          'Roboto',
          '"Helvetica Neue"',
          '"Segoe UI"',
          '"Apple SD Gothic Neo"',
          '"Noto Sans KR"',
          '"Malgun Gothic"',
          'sans-serif',
        ],
      },
      typography: {
        DEFAULT: {
          css: {
            maxWidth: '100%',
            color: '#1e293b',
            fontSize: '1.1875rem', // 19px base font size for seniors!
            lineHeight: '1.9',      // Relaxed line-height for aging eyes
            a: {
              color: '#b8860b',
              fontWeight: '600',
              textDecoration: 'underline',
              textUnderlineOffset: '4px',
              '&:hover': {
                color: '#946608',
              },
            },
            h1: { color: '#0f172a', fontWeight: '800', lineHeight: '1.3' },
            h2: {
              color: '#0f172a',
              fontWeight: '700',
              marginTop: '2em',
              marginBottom: '0.7em',
              paddingBottom: '0.3em',
              borderBottom: '2px solid #fef3c7',
            },
            h3: { color: '#1e293b', fontWeight: '700', marginTop: '1.6em', marginBottom: '0.6em' },
            strong: { color: '#0f172a', fontWeight: '700' },
            p: { marginTop: '1.2em', marginBottom: '1.2em' },
            li: { marginTop: '0.5em', marginBottom: '0.5em' },
            code: {
              color: '#0f172a',
              backgroundColor: '#fef3c7',
              padding: '0.2em 0.4em',
              borderRadius: '0.25rem',
              fontWeight: '600',
            },
            'code::before': { content: '""' },
            'code::after': { content: '""' },
          },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
};
