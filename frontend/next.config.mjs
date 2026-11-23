/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  images: {
    dangerouslyAllowSVG: false,
    contentDispositionType: "attachment",
    contentSecurityPolicy: "default-src 'self'; script-src 'none'; sandbox;",
    remotePatterns: [
      { protocol: "https", hostname: "themetroscope.com" },
      { protocol: "https", hostname: "api.themetroscope.com" },
      { protocol: "https", hostname: "images.unsplash.com" },
      { protocol: "https", hostname: "**.reuters.com" },
      { protocol: "https", hostname: "**.bbci.co.uk" },
      { protocol: "https", hostname: "**.bloomberg.com" },
      { protocol: "https", hostname: "**.wsj.net" },
      { protocol: "https", hostname: "**.nasa.gov" },
      { protocol: "https", hostname: "**.whitehouse.gov" },
      { protocol: "https", hostname: "**.state.gov" },
      { protocol: "https", hostname: "**.energy.gov" },
      { protocol: "https", hostname: "**.arcpublishing.com" },
      { protocol: "https", hostname: "**.townnews.com" },
      { protocol: "https", hostname: "**.brightspot.s3.amazonaws.com" },
      { protocol: "https", hostname: "**.cloudfront.net" },
      { protocol: "https", hostname: "**.imgix.net" },
      { protocol: "https", hostname: "**.espncdn.com" },
      { protocol: "https", hostname: "**.cbsistatic.com" },
      { protocol: "https", hostname: "**.cbsig.net" },
      { protocol: "https", hostname: "**.b-cdn.net" },
      { protocol: "https", hostname: "**.globenewswire.com" },
    ],
  },
  async rewrites() {
    const backendApiBase = (
      process.env.INTERNAL_API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://127.0.0.1:8000/api/v1"
    ).replace(/\/$/, "");
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendApiBase}/:path*`,
      },
    ];
  },
};

export default nextConfig;
