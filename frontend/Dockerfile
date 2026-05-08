FROM node:22-alpine

WORKDIR /app

# Enable corepack to use pnpm
RUN corepack enable pnpm

# Install dependencies first (for better caching)
COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml* ./
RUN pnpm install --no-frozen-lockfile

# Copy all project files
COPY . .

EXPOSE 3000

# Start Next.js in development mode (with hot reloading)
CMD ["pnpm", "run", "dev"]
