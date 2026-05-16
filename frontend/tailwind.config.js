/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        heebo: ["Heebo", "Rubik", "Arial", "sans-serif"],
      },
      colors: {
        brand: {
          50:  "#eef6ff",
          100: "#dceeff",
          500: "#1e60f0",
          600: "#1450d8",
          700: "#0e3fae",
          900: "#0b2a73",
        },
      },
    },
  },
  plugins: [],
};
