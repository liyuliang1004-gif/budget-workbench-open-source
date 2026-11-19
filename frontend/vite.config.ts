import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

const isV2 = process.env.npm_lifecycle_event === "dev:v2" || process.env.npm_lifecycle_event === "build:v2";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    proxy: {
      "/api": "http://127.0.0.1:8000"
    },
    open: isV2 ? "/index_v2.html#/home" : false
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        main_v2: resolve(__dirname, "index_v2.html")
      }
    }
  }
});
