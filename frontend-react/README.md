# SimplyDoc React frontend

The maintained app uses React and Vite. See the project-root README for full startup and deployment instructions.

- npm ci
- npm run dev (backend must be running at 127.0.0.1:8000)
- npm run lint
- npm run build

Production uses relative /api routes and HTTP-only cookies. FastAPI serves dist/ from the same origin. Never put API keys in VITE_ variables.
