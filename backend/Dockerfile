FROM python:3.14-slim

RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources

ENV PYTHONUNBUFFERED=1 \   Env pythonunbuffered =1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app   WORKDIR /应用程序

RUN apt-get update && apt-get install -y --no-install-recommends \执行命令apt-get update &；&
    gcc \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*&& rm -rf /var/lib/apt/list /*

COPY requirements.txt .   COPY requirements.txt。

RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY backend/ ./

RUN mkdir -p /app/data   执行mkdir -p /app/data命令

EXPOSE 8000   8000年公开

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
