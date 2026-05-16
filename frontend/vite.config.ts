import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/**
 * Dev server config.
 *
 * - host: 0.0.0.0 → reachable from phone on the same Wi-Fi at http://<PC_IP>:5173
 * - proxy: forwards /api/* to the FastAPI backend
 *
 * Override the backend target with VITE_BACKEND_URL if running on a different
 * host/port (e.g. a remote dev box).
 */
const backendTarget = process.env.VITE_BACKEND_URL || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // 0.0.0.0 — accept LAN connections
    port: 5173,
    // Vite 5 has strict DNS-rebinding protection.  Allow common
    // reverse-tunnel hosts so phone/remote access via localhost.run or
    // Cloudflare quick tunnels works while we're testing remotely.
    allowedHosts: [".lhr.life", ".localhost.run", ".trycloudflare.com", "localhost"],
    proxy: {
      "/api": {
        target: backendTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  preview: {
    host: true,
    port: 5173,
    allowedHosts: [".lhr.life", ".localhost.run", ".trycloudflare.com", "localhost"],
  },
});
