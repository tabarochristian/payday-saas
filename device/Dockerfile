# Use an official Python runtime as a parent image
FROM python:lastest

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY device/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY device/ .