# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Install system tools, add Microsoft's custom repository, and install the ODBC Driver 17
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    gcc \
    g++ \
    unixodbc-dev \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && apt-get clean -y

# Set the working directory inside the container
WORKDIR /app

# Copy your requirements and install Python libraries
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all your Python code into the container
COPY . .

# Expose port 7860 (The port Hugging Face looks for)
EXPOSE 5000

# Start the Flask app using Gunicorn on port 7860
CMD ["gunicorn", "-b", "0.0.0.0:7860", "app:app"]
