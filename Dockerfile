FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd -m appuser

# Create the data directory with proper permissions
RUN mkdir -p data && \
    chown -R appuser:appuser /app data && \
    chmod 755 data

# Switch to non-root user
USER appuser

# Copy requirements first to leverage Docker cache
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Add local bin to PATH
ENV PATH="/home/appuser/.local/bin:${PATH}"

# Copy the rest of the application
COPY --chown=appuser:appuser . .

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

# Expose the port the app runs on
EXPOSE 5000

# Command to run the application
CMD ["python", "app.py"] 