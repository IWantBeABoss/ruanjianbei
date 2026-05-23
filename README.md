# 软件杯项目

## 方式一：VS Code Dev Container（用这个简单一点）

队友 clone 后无需安装任何环境，VS Code 自动完成所有配置。

### 前置要求
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)（应用商店可下载）
- [VS Code](https://code.visualstudio.com/) + [Dev Containers 插件](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

### 启动步骤
1. 打开终端，clone 项目并进入目录
2. 把 `backend/.env.example` 改名为 `.env`，把 `.env` 里标记了的地方改为群里发的 apikey（注意把对应的 `#` 删掉）
3. 用 VS Code 打开项目
4. 右下角弹出提示 **"Reopen in Container"**，点击即可

首次启动需要构建镜像（约 3-5 分钟），之后秒开。

进入容器后：
- **后端**自动运行在 `http://localhost:8000`，代码修改自动热重载
- **前端**自动运行在 `http://localhost:5173`，支持 HMR 热更新

如果没有弹出提示，按 `Ctrl+Shift+P` → 输入 `Dev Containers: Reopen in Container`。

---

## 方式二：Docker Compose（传统方式）

### 前置要求
- 安装并配置好 [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### 启动步骤
1. 打开终端（Win + X → 终端），clone 项目并进入目录
2. 把 `backend/.env.example` 改名为 `.env`，把 `.env` 里标记了的地方改为群里发的 apikey（注意把对应的 `#` 删掉）
3. 运行 `docker-compose up -d`
4. 访问 `http://localhost:8080`
