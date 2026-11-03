# Security policy

## Supported versions

QPyServe is an early-alpha project. Fixes are developed on `main` and published in
subsequent releases. PyPI versions do not automatically include unreleased GitHub fixes.

## Reporting a vulnerability

Do not open a public issue with exploits, credentials, or sensitive logs. Use
GitHub's **Report a vulnerability** option under the repository's Security tab
if enabled. Otherwise, contact the maintainer privately before public disclosure.

## Security responsibilities

QPyServe orchestrates FastAPI and static frontend assets. It is not an
authentication system, firewall, HTTPS proxy, rate limiter, or security scanner.
Applications must:

- Authenticate and authorize every protected FastAPI endpoint.
- Configure CORS with explicit trusted origins when cross-origin access is needed.
  CORS does not block direct API requests from non-browser clients.
- Protect state-changing cookie-authenticated routes against CSRF and set safe cookie flags.
- Deploy behind HTTPS with appropriate networking and forwarded-header controls.
- Validate user input, limit request sizes/rates, and monitor logs.
- Keep private data and credentials outside the served frontend folder and JS bundles.
- Never expose a Vite development server publicly.
- Use shared storage for multi-worker application state.

## Default defenses

QPyServe rejects file traversal and symlinks escaping the static root, blocks hidden
files/source/keys and unknown file extensions, and sends
`X-Content-Type-Options: nosniff` on static responses. Development runs on loopback.
Missing API routes do not fall back to the SPA HTML page.

This is defense in depth, **not** permission to place secrets under the frontend
directory. A deliberately public `data.json` will still be served.
