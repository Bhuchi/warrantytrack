import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,

  /**
   * Same-origin access to the API.
   *
   * The browser calls `/api/*`, which is rewritten to the FastAPI service with
   * the `/api` prefix stripped — so the backend keeps serving `/health`,
   * `/assets` and the rest at its root, unchanged.
   *
   * This is what lets `NEXT_PUBLIC_API_URL` be a relative `/api` in the
   * deployed image: no CORS, and no need to know the load balancer hostname
   * when the image is built. On ECS both containers share one network
   * namespace, so the API is on loopback.
   *
   * Local development is unaffected: `.env.local` points NEXT_PUBLIC_API_URL
   * straight at http://localhost:8000, which bypasses this rewrite entirely.
   */
  async rewrites() {
    const apiUrl = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${apiUrl}/:path*` }];
  },
};

export default nextConfig;
