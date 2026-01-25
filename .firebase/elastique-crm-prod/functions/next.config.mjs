// member_dashboard/next.config.mjs
var nextConfig = {
  // Rewrites allow proxying API calls to the Python backend
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*"
        // Python FastAPI
      }
    ];
  }
};
var next_config_default = nextConfig;
export {
  next_config_default as default
};
