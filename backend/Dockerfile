# # In backend/Dockerfile

# FROM python:3.10-slim

# WORKDIR /app

# # --- THE FIX: Install curl so the healthcheck can run ---
# RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# # Copy the requirements file first to leverage Docker's build cache
# COPY requirements.txt requirements.txt

# # Install all Python dependencies from the requirements file
# RUN pip install --no-cache-dir -r requirements.txt

# # Install the browsers needed by Playwright
# RUN playwright install

# # Now, copy the rest of your application code
# COPY . .

# # The command to run when the container starts
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning"]
# Use the official Microsoft Playwright image
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set the working directory
WORKDIR /app

# Copy and install Python dependencies from the requirements file
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# This command installs the necessary browser binaries for Playwright
RUN playwright install

# Copy the rest of your application code
COPY . .

# Expose the port
EXPOSE 8000

# Set the command to run the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning"]