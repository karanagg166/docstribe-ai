FROM python:3.12-slim

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production

WORKDIR /app

# Create a non-root user
RUN groupadd -r docstribe && useradd -r -g docstribe docstribe

# Install dependencies first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Change ownership of the app directory to the non-root user
RUN chown -R docstribe:docstribe /app

# Switch to non-root user
USER docstribe

EXPOSE 8000

# Run uvicorn server for production (without --reload)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
