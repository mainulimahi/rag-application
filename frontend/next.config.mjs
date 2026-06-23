/** @type {import('next').NextConfig} */
const nextConfig = {
  // Produces a self-contained Node.js server in .next/standalone — required for the
  // production Docker image (no node_modules in the runtime layer).
  output: 'standalone',
  // react-markdown and remark-gfm are ESM-only; Next.js needs to transpile them.
  transpilePackages: ['react-markdown', 'remark-gfm'],
}

export default nextConfig
