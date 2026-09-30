import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Saída em dist/: o Coolify publica essa pasta (Nixpacks, "site estático", Publish Directory /dist).
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist", assetsInlineLimit: 0 },
});
