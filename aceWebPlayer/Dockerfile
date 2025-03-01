# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create resources directory if it doesn't exist
RUN mkdir -p resources

# Expose port 5000
EXPOSE 5000

RUN chmod a+x /app/run.sh

# Configurar entrypoint
ENTRYPOINT ["/app/run.sh"]
