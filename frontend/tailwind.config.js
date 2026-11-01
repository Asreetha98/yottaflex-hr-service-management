/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef6ff',
          100: '#d9eaff',
          500: '#2f6fdb',
          600: '#2559b8',
          700: '#1d4691',
        },
      },
    },
  },
  plugins: [],
};
