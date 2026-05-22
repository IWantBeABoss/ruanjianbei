# frontend/Dockerfile
# 阶段1：构建
FROM node:22-alpine AS builder

WORKDIR /app

# 复制依赖文件
COPY frontend/package*.json frontend/yarn.lock* frontend/pnpm-lock.yaml* ./

# 安装依赖（自动检测包管理器）
RUN if [ -f package-lock.json ]; then npm ci; \
    elif [ -f yarn.lock ]; then yarn --frozen-lockfile; \
    elif [ -f pnpm-lock.yaml ]; then corepack enable pnpm && pnpm install --frozen-lockfile; \
    else npm install; fi

# 复制前端源码
COPY frontend/ ./

# 构建生产版本
RUN npm run build

# 阶段2：运行
FROM nginx:alpine

# 复制 nginx 配置（支持 SPA 路由和 API 代理）
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]