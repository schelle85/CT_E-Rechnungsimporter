FROM node:22-alpine@sha256:0e1754758c2df4cfa3e68d59e2e1b7374bb7fd9ea6328eaaacf15cc934af8202 AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build
FROM nginxinc/nginx-unprivileged:1.28-alpine@sha256:7377697a821c131a924a7105fafbe7414db4e9fcc77a6f08f776f33f141ec3f8
COPY --from=build /app/dist /usr/share/nginx/html
COPY deploy/nginx/nginx.conf /etc/nginx/nginx.conf
USER 10002:10002
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]
