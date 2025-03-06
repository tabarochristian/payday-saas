# Use an official Python runtime as a parent image
FROM python:3.12.2-slim

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app/

# Install the required packages
RUN pip install --no-cache-dir redis flower

# PYTHONUNBUFFERED: Force stdin, stdout and stderr to be totally unbuffered. (equivalent to `python -u`)
# PYTHONHASHSEED: Enable hash randomization (equivalent to `python -R`)
# PYTHONDONTWRITEBYTECODE: Do not write byte files to disk, since we maintain it as readonly. (equivalent to `python -B`)
ENV PYTHONUNBUFFERED=1 PYTHONHASHSEED=random PYTHONDONTWRITEBYTECODE=1

# Make port 5555 available to the world outside this container
EXPOSE 5555

ENV FLOWER_DATA_DIR /data
ENV PYTHONPATH ${FLOWER_DATA_DIR}

WORKDIR $FLOWER_DATA_DIR

# Add a user with an explicit UID/GID and create necessary directories
RUN set -eux; \
    addgroup -g 1000 flower; \
    adduser -u 1000 -G flower flower -D; \
    mkdir -p "$FLOWER_DATA_DIR"; \
    chown flower:flower "$FLOWER_DATA_DIR"
USER flower

VOLUME $FLOWER_DATA_DIR

CMD ["celery", "flower"]
