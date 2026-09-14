import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow accessing the dev server from this specific device on the local network
  // @ts-ignore - allowedDevOrigins might not be in the strict NextConfig types yet depending on version
  allowedDevOrigins: ['10.19.204.100'],
};

export default nextConfig;
