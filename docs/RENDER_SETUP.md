# Render setup

Render is a convenient first private runtime for Dante X because it can deploy the repository's Dockerfile and lets the owner enter secrets directly in its dashboard.

1. Sign in to Render using GitHub.
2. Create a new Blueprint/Web Service from the private `Dante-X` repository.
3. Select the `build/foundation` branch while the foundation PR remains open.
4. Render will detect `render.yaml`.
5. In the Render dashboard, enter `UPSTOX_ANALYTICS_TOKEN` yourself when prompted. Do not send it to ChatGPT.
6. Keep `DANTEX_MODE=shadow`.
7. Deploy.
8. Confirm the health endpoint before connecting the provider.

The token remains a server-side Render secret. Do not mark it as a public/client-side variable.

After CI, provider connection, and validation gates are complete, deployment can be promoted deliberately. Do not switch to live mode merely because the service starts successfully.
