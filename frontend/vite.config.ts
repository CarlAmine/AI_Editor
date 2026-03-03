import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite config for the AI Editor UI.
// API base URL is controlled from the front-end via VITE_API_BASE_URL env var.

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  preview: {
    port: 4173,
  },
});

