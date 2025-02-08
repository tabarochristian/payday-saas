FROM certbot/certbot:latest

# Install dependencies and add the Certbot PPA (for Debian/Ubuntu-based images)
RUN apt-get update && \
    apt-get install -y software-properties-common && \
    add-apt-repository ppa:certbot/certbot && \
    apt-get update && \
    apt-get install -y certbot python3-certbot-dns-digitalocean && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*