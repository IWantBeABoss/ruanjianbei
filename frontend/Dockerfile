FROM node:22-alpine AS builder

WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./

RUN npx vite build

FROM python:3.14-alpine

WORKDIR /app
COPY --from=builder /app/dist /app/html

EXPOSE 80

CMD ["python", "-m", "http.server", "80", "--directory", "/app/html"]