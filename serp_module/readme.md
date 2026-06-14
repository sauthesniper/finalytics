# MDS Company Website Finder API

Dockerized FastAPI service that receives a company name and returns the most likely official website using SerpAPI, domain filtering, and confidence scoring.

## Features

- FastAPI-based REST API
- API key authentication using `x-api-key`
- Company website discovery from company name
- SerpAPI integration for real web search results
- Filtering for non-official domains such as LinkedIn, Facebook, Wikipedia, Reddit, YouTube, etc.
- Confidence scoring for candidate websites
- Minimum confidence threshold to avoid weak matches
- Dockerized deployment with Docker Compose
- Swagger UI documentation at `/docs`

## Tech Stack

- Python
- FastAPI
- Uvicorn
- Pydantic
- Requests
- SerpAPI
- Docker
- Docker Compose

## Project Structure

```text
app/
├── __init__.py
├── main.py       # FastAPI app, routes, API key validation
├── requests.py   # Request and response models
├── findweb.py    # Main website discovery logic
├── search.py     # SerpAPI integration
├── filters.py    # Blocked/irrelevant domains
├── scoring.py    # Confidence scoring logic
└── utils.py      # Helper functions

Dockerfile
docker-compose.yml
requirements.txt
.env.example
.gitignore
README.md
```

## Environment Variables

Create a `.env` file in the project root.

Example:

```env
API_KEY=dev-secret-key
PORT=3000
SERPAPI_API_KEY=your-serpapi-key
```

Do not commit `.env` to GitHub.

The `.env.example` file contains placeholder values:

```env
API_KEY=change-me
PORT=3000
SERPAPI_API_KEY=change-me
```

## Run with Docker

Make sure Docker Desktop is running.

Then start the service:

```bash
docker compose up --build
```

The API will be available at:

```text
http://127.0.0.1:3000
```

Swagger documentation:

```text
http://127.0.0.1:3000/docs
```

## API Endpoints

### Health Check

```http
GET /health
```

Example response:

```json
{
  "status": "ok"
}
```

### Discover Company Website

```http
POST /discover
```

Required header:

```text
x-api-key: dev-secret-key
```

Request body:

```json
{
  "companyName": "UiPath"
}
```

Example response:

```json
{
  "companyName": "UiPath",
  "website": "https://www.uipath.com",
  "domain": "uipath.com",
  "confidence": 0.95,
  "status": "found",
  "alternatives": [
    {
      "title": "UiPath: AI and Automation Platform",
      "url": "https://www.uipath.com",
      "domain": "uipath.com",
      "score": 0.95
    }
  ],
  "error": null
}
```

If no reliable result is found:

```json
{
  "companyName": "unknown test company",
  "website": null,
  "domain": null,
  "confidence": 0.17,
  "status": "not_found",
  "alternatives": [],
  "error": "No candidate passed the minimum confidence threshold."
}
```

## How It Works

The service follows this flow:

```text
companyName
→ SerpAPI search
→ organic search results
→ blocked domain filtering
→ confidence scoring
→ minimum threshold check
→ final JSON response
```

The API searches for:

```text
<companyName> official website
```

Then it removes non-official or low-value domains such as:

```text
linkedin.com
facebook.com
instagram.com
wikipedia.org
crunchbase.com
glassdoor.com
indeed.com
youtube.com
reddit.com
```

Each remaining candidate receives a confidence score based on:

- company name match in domain
- company name match in title
- company name match in URL
- result position
- presence of words like `official` or `home`

If the best score is below the minimum confidence threshold, the service returns `not_found`.

## Example cURL

```bash
curl -X POST http://127.0.0.1:3000/discover \
  -H "Content-Type: application/json" \
  -H "x-api-key: dev-secret-key" \
  -d '{
    "companyName": "UiPath"
  }'
```

## Notes

This project returns the most likely official website based on search results and scoring. It does not mathematically guarantee that the result is always the official website.

For better accuracy, a future version can add website validation using Crawlee, Playwright, or BeautifulSoup after the candidate website is found.
