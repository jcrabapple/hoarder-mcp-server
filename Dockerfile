FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port and run application
EXPOSE 8000
# The port variable might be different depending on the hosting platform
ENV PORT=8000
# Use 0.0.0.0 to listen on all interfaces within the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
