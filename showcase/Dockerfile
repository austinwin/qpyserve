FROM node:22-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN NODE_OPTIONS=--max-old-space-size=4096 npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py geoengine.py smoke_test.py Dockerfile ./
RUN python smoke_test.py
COPY frontend/package.json ./frontend/
COPY frontend/src ./frontend/src
COPY frontend/public ./frontend/public
COPY --from=frontend-build /build/frontend/dist ./frontend/dist
EXPOSE 10000
CMD ["python", "main.py", "--prod"]
