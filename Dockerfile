# Underworld Simulation Environment Dockerfile
FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PORT=7788 \
    HOST=0.0.0.0 \
    UNDERWORLD_API_URL=http://127.0.0.1:7788

WORKDIR /app

# Install system utilities (curl for container healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy packaging configuration, readme, and source files for editable install
COPY pyproject.toml requirements.txt README.md ./
COPY src/ /app/src/

# Install project dependencies in editable mode
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e ".[dev]"

# Copy remaining project files
COPY main.py /app/main.py
COPY configs/ /app/configs/
COPY docs/ /app/docs/

# Create logs directory for persistent telemetry
RUN mkdir -p /app/logs

# Expose API and Web Dashboard port
EXPOSE 7788

# Health check ensuring API and Dashboard are responsive
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://127.0.0.1:7788/api/info || exit 1

# Default command: FastAPI with live hot-reloading for on-the-fly manipulations
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7788", "--reload", "--reload-dir", "/app/src"]
