FROM node:22-alpine AS   作为 builder

WORKDIR /app   WORKDIR /应用程序

COPY frontend/package*.json ./复制前端/包*。json。/
RUN npm ci
COPY frontend/ ./   COPY前端/ ./

RUN npx vite build   运行npx vite build

FROM python:3.14-alpine   从python 3.14高山

WORKDIR /app   WORKDIR /应用程序
COPY --from=builder /app/dist /app/htmlCOPY——from=builder /app/dist /app/html

EXPOSE 80   80年公开

CMD ["python", "-m", "http.server", "80", "--directory", "/app/html"]CMD ["python", "-m", "http.server", "80", "--directory", "/app/html"]
