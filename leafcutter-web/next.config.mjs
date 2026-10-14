/** @type {import('next').NextConfig} */
const nextConfig = {
  // Let a trailing slash reach middleware.ts unchanged: Next.js's own 308 would
  // turn /flows/<product>/<flow>/ into the canonical flow address. Middleware
  // re-implements the slash-less 308 for every other path (UXP-591-1-iii).
  skipTrailingSlashRedirect: true,
};

export default nextConfig;
