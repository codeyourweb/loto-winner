import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// The proxy avoids any CORS issue in development:
// the front end calls /api/... and Vite forwards it to Flask.
//
// The target port is configurable through the environment variable
// `LOTO_BACKEND_PORT` (or `VITE_BACKEND_PORT`), which lets the launch scripts
// use a port other than 5000.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backendPort = env.LOTO_BACKEND_PORT || env.VITE_BACKEND_PORT || "5000";
  const backendTarget = env.VITE_API_PROXY_TARGET || `http://127.0.0.1:${backendPort}`;

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: backendTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
