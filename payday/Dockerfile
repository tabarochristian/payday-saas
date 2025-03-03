# Use an official Python runtime as a parent image
FROM python:3.12.2-slim

# Install Git
RUN apt-get update && apt-get install -y git

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY payday/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --upgrade --force-reinstall -r requirements.txt

# Copy the rest of the application code
COPY payday/ .