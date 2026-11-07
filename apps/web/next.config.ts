import type { NextConfig } from "next";
import path from "node:path";
import { API_PREFIX, DEFAULT_API_URL } from "../../packages/contracts/api";

const config: NextConfig = {
  turbopack: { root: path.resolve(__dirname, "../..") },
  async rewrites() {
    return [{ source: `${API_PREFIX}/:path*`, destination: `${(process.env.API_URL || DEFAULT_API_URL).replace(/\/$/, "")}${API_PREFIX}/:path*` }];
  },
};
export default config;
