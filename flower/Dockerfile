# Use an official Python runtime as a parent image
FROM python:3.12.2-slim

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app/

# Install flower
RUN pip install flower

# Make port 8000 available to the world outside this container
EXPOSE 8000
