#!/bin/bash
set -e

# Step 1: Install prerequisites
echo "Installing prerequisites..."
apt update
apt install -y curl gnupg lsb-release

# Step 2: Add Dalibo Labs APT repository
echo "Adding Dalibo Labs repository..."
echo "deb [arch=amd64] http://apt.dalibo.org/labs bullseye-dalibo main" > /etc/apt/sources.list.d/dalibo-labs.list
curl -fsSL -o /etc/apt/trusted.gpg.d/dalibo-labs.gpg https://apt.dalibo.org/labs/debian-dalibo.gpg

# Step 3: Install PostgreSQL Anonymizer
echo "Installing PostgreSQL Anonymizer..."
apt update
apt install -y postgresql_anonymizer_17

echo "PostgreSQL Anonymizer setup completed!"