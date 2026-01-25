/** @type {import('next').NextConfig} */
const nextConfig = {
    // Rewrites allow proxying API calls to the Python backend
    async rewrites() {
        // Use Cloud Run backend in production, localhost in dev
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
        return [
            {
                source: '/api/:path*',
                destination: `${backendUrl}/api/:path*`,
            },
        ];
    },
};

export default nextConfig;
