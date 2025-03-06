# Use an official Python runtime as a parent image
FROM python:3.12.2-slim

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . /app/

# Install flower
RUN pip install flower

EXPOSE 8000
