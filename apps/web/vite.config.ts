import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "KOYORI_");
  const proxy = {
    "/v1": { target: env.KOYORI_API_TARGET || "http://127.0.0.1:8088" },
  };
  return {
    plugins: [react()],
    server: { port: 5178, strictPort: true, proxy },
    preview: { port: 4178, strictPort: true, proxy },
  };
});
