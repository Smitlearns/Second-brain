import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, Vite serves the React app and passes API calls on to FastAPI (see run.py)
const backend = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": backend,
      "/flask": backend,
    },
  },
});
