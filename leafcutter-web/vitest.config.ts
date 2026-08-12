import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Test harness for the Atlas. Component tests run in jsdom; pure data-layer
// tests (lib/data/**) run fine there too. The "@/..." alias mirrors tsconfig
// ("@/*" -> "./*").
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["**/*.test.{ts,tsx}"],
    exclude: ["node_modules/**", ".next/**", "fixtures/**"],
  },
});
