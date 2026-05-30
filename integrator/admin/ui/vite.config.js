import { defineConfig } from "vite";

export default defineConfig({
  base: "/admin/",
  root: ".",
  build: {
    outDir: "../static/dist",
    emptyOutDir: true,
    assetsDir: "assets",
  },
  server: {
    proxy: {
      "/admin/api": "http://127.0.0.1:17320",
    },
  },
});
