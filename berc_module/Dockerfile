FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libcairo2 \
    libx11-xcb1 \
    libxcb1 \
    libxext6 \
    libx11-6 \
    fonts-liberation \
    libappindicator3-1 \
    xdg-utils \
    libdbus-glib-1-2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

COPY pdf_to_json.py .
COPY api.py .

RUN mkdir -p /app/data_pdf /app/data_json /tmp/berc_profile

EXPOSE 8001

CMD ["python3", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8001"]
