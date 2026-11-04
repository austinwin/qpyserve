# QPyServe — Live Showcase

A real FastAPI + React/Vite app, served by QPyServe from a single origin.

- **Playground:** POST /api/flow (real Pydantic-validated Python computation)
- **Source explorer:** public allowlist of backend, frontend and deployment files
- **FastAPI docs:** /docs
- **Health check:** /api/health

## Local development

\`\`\`sh
pip install -r requirements.txt
cd frontend && npm install && cd ..
python main.py
\`\`\`

## Render

Create a free Docker web service from this repo's \`showcase/render-live-demo\` branch:
- Dockerfile path: \`showcase/Dockerfile\`
- Docker context: \`showcase\`
- Port: \`10000\` (Docker CMD reads Render's PORT)

Static frontend builds in Node, Python runtime uses QPyServe 0.4.0.
Source API never exposes arbitrary server files or environment variables.
