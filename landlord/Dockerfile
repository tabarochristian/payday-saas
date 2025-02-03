# Use an official Python runtime as a parent image
FROM python:3.12.2-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY landlord/requirements.txt .

# Install apt dependencies
RUN apt-get update && apt-get install -y libz-dev libjpeg-dev libfreetype6-dev python-dev

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY landlord/ .