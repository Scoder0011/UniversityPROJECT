# Use Ubuntu base with Python
FROM ubuntu:22.04

# Prevent prompts during install
ENV DEBIAN_FRONTEND=noninteractive

# Install Python + LibreOffice (needed for doc conversions) + other tools
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    libreoffice libreoffice-writer libreoffice-impress \
    poppler-utils qpdf \
    fonts-dejavu-core fonts-dejavu-extra \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory inside the container
WORKDIR /app

# Copy requirements first (so Docker caches pip installs)
COPY requirements.txt /app/requirements.txt
RUN pip3 install --upgrade pip
RUN pip3 install -r /app/requirements.txt

# Copy the rest of your backend code
COPY . /app

# Set environment variable for port
ENV PORT=5000
EXPOSE 5000

# Start the app with Gunicorn (production server for Flask)
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000", "--workers", "3", "--timeout", "300"]
