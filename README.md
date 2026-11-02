# Product Newsletter Generator

A small FastAPI web application that accepts product codes and campaign prices, scrapes the COMPANY catalogue, renders the existing newsletter HTML, and provides a preview/download. It can also send the generated HTML by SMTP.

This approach to retrieving product data was chosen because no API or other automation interface for accessing the catalogue data was available.

The newsletter markup is in `templates/newsletter.html`; edit the template separately from the scraping and generation code.

## Mistral product descriptions

Set `MISTRAL_API_KEY` in `.env` to enable Czech marketing descriptions. The application loads `.env` locally, and Docker Compose passes the same file to the container. A `MISTRAL_API_KEY` already set in the process environment takes precedence. Without a key, the scraped product description is used as-is. Mistral request failures are reported rather than silently replaced with placeholder text.

## Run locally

```powershell
Copy-Item .env.example .env
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload
```

Open <http://127.0.0.1:8000>. Enter one item per line:

```text
26929842 - 42 599 Kč
26930988 - 3 199 Kč
```

A Chromium installation is required for local Selenium runs. The Docker setup includes it automatically.

## Deploy on Debian VPS

1. Install Docker Engine and the Compose plugin.
2. Copy the project to the VPS and create `.env` from `.env.example`.
3. Set a strong `APP_API_KEY`. Keep port `8000` behind HTTPS and a reverse proxy such as Caddy or Nginx.
4. Start the service:

```bash
docker compose up -d --build
```

The generated files persist in `./output`. The service intentionally runs one scrape at a time because catalogue scraping is the expensive operation and the target VPS has two vCPUs.

## Email

Leave the email field empty to only preview/download. To enable email delivery, set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM` in `.env`, then enter a recipient in the UI.

Never commit `.env` or API keys.
