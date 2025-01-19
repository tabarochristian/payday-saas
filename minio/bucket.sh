#!/bin/sh

# Wait for MinIO to be ready
echo "Waiting for MinIO to be ready..."
until curl -s http://minio:9000; do
  sleep 1
done

echo "MinIO is ready. Creating buckets..."

# Configure MinIO Client
mc alias set local http://minio:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD

# Create the bucket
mc mb local/$MINIO_BUCKET_NAME

# Set the bucket policy to public (read-only)
mc policy set public local/$MINIO_BUCKET_NAME

echo "Bucket '$MINIO_BUCKET_NAME' created and set to public."