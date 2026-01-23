import type { NextConfig } from "next";

const distDir = process.env.NEXT_DIST_DIR?.trim() || ".next";

const nextConfig: NextConfig = {
  /* config options here */
  distDir,
  reactCompiler: true,

  // Enable standalone output for Docker deployments
  output: "standalone",

  images: {
    remotePatterns: [
      { protocol: "https", hostname: "m.media-amazon.com" },
      { protocol: "https", hostname: "images-na.ssl-images-amazon.com" },
      { protocol: "https", hostname: "images-eu.ssl-images-amazon.com" },
    ],
  },

  // Enable experimental features
  experimental: {
    // Optimize package imports
    optimizePackageImports: ["lucide-react", "@radix-ui/react-icons"],
  },
};

export default nextConfig;
