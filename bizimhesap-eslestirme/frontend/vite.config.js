import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
  test: {
    environment: "jsdom", environmentOptions: { jsdom: { url: "http://localhost:5173" } },
    env: { VITE_API_BASE: "http://localhost:8000/api" }, setupFiles: ["./src/test-setup.js"],
    testTimeout: 20000, fileParallelism: false,
  },
});
