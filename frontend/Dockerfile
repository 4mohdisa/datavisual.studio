# Next.js frontend (standalone output). Build from the frontend/ directory:
#   docker build -t datavisual-frontend frontend/
# Clerk publishable key is baked in at build time (it's public by design):
#   --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...
FROM node:22-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
RUN npm run build

FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
