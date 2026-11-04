FROM node:22-alpine AS ui
WORKDIR /build/frontend
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py ./
COPY Dockerfile ./
COPY frontend/package.json frontend/vite.config.js frontend/index.html ./frontend/
COPY frontend/src ./frontend/src
COPY --from=ui /build/frontend/dist ./frontend/dist
EXPOSE 10000
CMD ["python", "main.py", "--prod"]
