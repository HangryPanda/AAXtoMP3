# Production Dockerfile for Audible Library Web
# Multi-stage build with Next.js standalone output

# ===========================================
# Stage 1: Install dependencies
# ===========================================
FROM node:20-alpine AS deps

WORKDIR /app

# Install dependencies
COPY apps/web/package.json apps/web/package-lock.json* ./
RUN npm ci --only=production

# ===========================================
# Stage 2: Build application
# ===========================================
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependencies
COPY --from=deps /app/node_modules ./node_modules

# Copy source code
COPY apps/web/ .

# Set build-time environment variables
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

# Build application
RUN npm run build

# ===========================================
# Stage 3: Production runner
# ===========================================
FROM node:20-alpine AS runner

WORKDIR /app

# Install curl for health checks
RUN apk add --no-cache curl bash

# Create non-root user
RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

# Set environment variables
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME="0.0.0.0"

# Copy entrypoint script
COPY docker/scripts/entrypoint-web.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Copy built application
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl --fail http://localhost:3000/api/health || exit 1

# Run application via entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
