FROM python:3.12-slim

# Install system dependencies for GeoDjango
RUN apt-get update && apt-get install -y \
    binutils \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libspatialindex-dev \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set GDAL and GEOS paths (important for Python bindings)
ENV GDAL_LIBRARY_PATH=/usr/lib/libgdal.so
ENV GEOS_LIBRARY_PATH=/usr/lib/libgeos_c.so

WORKDIR /app

# Install Python dependencies
COPY payday/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY payday/ .
