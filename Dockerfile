# Use Python 3.12 slim image
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y libpq-dev && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy all files
COPY . .

# Install dependencies
# Force install specific legacy version of langchain-core
RUN pip install langchain-core==0.1.52

RUN pip install --no-cache-dir -e .

# Expose port
EXPOSE 8000

# Run the app
CMD ["python", "-m", "src.api.main"]