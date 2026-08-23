/** @type {import('next').NextConfig} */
// NEXT_OUTPUT=export → static `out/` for single-container Render (Gyansetu-style).
// Default local/Docker frontend service keeps standalone + API rewrites.
const useExport = process.env.NEXT_OUTPUT === "export";

const nextConfig = {
  ...(useExport
    ? {
        output: "export",
        images: { unoptimized: true },
        trailingSlash: true,
      }
    : {
        output: "standalone",
        async rewrites() {
          return [
            {
              source: "/api/:path*",
              destination: `${
                process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
              }/api/:path*`,
            },
          ];
        },
      }),
};

module.exports = nextConfig;

