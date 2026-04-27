// @ts-check
import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://simulation-bench.fly.dev",
  build: {
    format: "directory",
  },
  markdown: {
    shikiConfig: {
      theme: "github-dark",
      wrap: true,
    },
  },
});
