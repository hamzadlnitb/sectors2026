import type { NextConfig } from "next";

// PANTAU web = static-only. Zero server runtime, zero API/LLM at runtime [AD-1].
// `output: "export"` emits pure static HTML/JSON into out/ — deployable anywhere,
// and structurally incapable of calling Sectors or an LLM while a judge watches.
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
