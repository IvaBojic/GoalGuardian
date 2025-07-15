FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Add source code and startup files
COPY . .
RUN chmod +x /app/start.sh

# Expose FastAPI port
EXPOSE 8000

# Use start.sh to control logging
ENTRYPOINT ["/app/start.sh"]
