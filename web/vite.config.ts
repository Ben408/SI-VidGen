import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Bind IPv4 explicitly — on Windows, default "localhost" often lands on ::1 only,
    // so http://127.0.0.1:5173 fails while http://localhost:5173 may 404 or miss.
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
