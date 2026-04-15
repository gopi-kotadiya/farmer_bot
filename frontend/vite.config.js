import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Long Groq / RAG calls can exceed default proxy timeouts → empty body + JSON parse errors
      "/v1": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        timeout: 600_000,
        proxyTimeout: 600_000,
      },
      "/health": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        timeout: 15_000,
        proxyTimeout: 15_000,
      },
    },
  },
});
