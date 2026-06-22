/** @type {import('next').NextConfig} */
const nextConfig = {
  // react-markdown and remark-gfm are ESM-only; Next.js needs to transpile them.
  transpilePackages: ['react-markdown', 'remark-gfm'],
}

export default nextConfig
