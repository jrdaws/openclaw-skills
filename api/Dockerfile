FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN adduser --disabled-password --no-create-home appuser
USER appuser

EXPOSE 8400

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8400", "--workers", "2"]
