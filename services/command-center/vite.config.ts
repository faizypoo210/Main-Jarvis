import path from "path";
import { fileURLToPath } from "url";

import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

/**
 * Dev server proxies /api and /health to the control plane and injects x-api-key from
 * CONTROL_PLANE_API_KEY (Node-only — never bundled into the client).
 */
export default defineConfig(({ mode }) => {
  const __dirname = path.dirname(fileURLToPath(import.meta.url));
  const env = loadEnv(mode, __dirname, "");
  const proxyTarget =
    env.VITE_CONTROL_PLANE_PROXY_TARGET ||
    env.CONTROL_PLANE_PROXY_TARGET ||
    "http://127.0.0.1:8001";
  const apiKey = env.CONTROL_PLANE_API_KEY || "";

  return {
    plugins: [react()],
    test: {
      environment: "jsdom",
      setupFiles: "./src/test/setup.ts",
      include: ["src/**/*.test.{ts,tsx}"],
    },
    server: {
      // Long-lived SSE: disable /api proxy socket timeouts (defaults can drop idle streams).
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
          timeout: 0,
          proxyTimeout: 0,
          configure: (proxy) => {
            proxy.on("proxyReq", (proxyReq) => {
              if (apiKey) {
                proxyReq.setHeader("x-api-key", apiKey);
              }
            });
          },
        },
        "/health": {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
