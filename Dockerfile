
FROM python:3.12-slim

WORKDIR /app

# Install the C++ compiler
RUN apt-get update && apt-get install -y g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project files
COPY . .

# Start the Flask application
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} app:app"]
