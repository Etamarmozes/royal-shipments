/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Heebo', 'Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        ink: '#0f172a',
        muted: '#475569',
        accent: '#1e3a8a',
      },
    },
  },
  plugins: [],
};
