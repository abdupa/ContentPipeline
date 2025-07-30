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