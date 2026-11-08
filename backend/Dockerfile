FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 /uv /uvx /usr/local/bin/
ENV UV_NO_CACHE=1 UV_PYTHON_DOWNLOADS=never

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production

WORKDIR /app

# Create a non-root user
RUN groupadd -r docstribe && useradd -r -g docstribe docstribe

# Install dependencies first for better caching
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Copy application code
COPY . .

# Change ownership of the app directory to the non-root user
RUN chown -R docstribe:docstribe /app

# Switch to non-root user
USER docstribe

EXPOSE 8000

# Run uvicorn server for production (without --reload)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
