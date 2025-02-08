FROM certbot/certbot:latest

# Install certbot-dns-digitalocean using apt
RUN apt-get update && \
    apt-get install -y certbot python3-certbot-dns-digitalocean && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*