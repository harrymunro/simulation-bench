# syntax=docker/dockerfile:1.6
FROM node:20-alpine AS build
WORKDIR /app
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci
COPY dashboard/ ./
COPY submissions/ ../submissions/
COPY SCORING_GUIDE.md RUN_PROTOCOL.md /app/repo-docs/
# At this point we expect Python-generated inputs (leaderboard.json, content/) to already
# exist on disk inside the build context (the Makefile runs build_dashboard.py first).
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile
EXPOSE 80
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
