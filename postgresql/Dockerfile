FROM postgres:latest

# Install necessary packages
RUN apt-get update && \
    apt install curl lsb-release echo deb http://apt.dalibo.org/labs $(lsb_release -cs)-dalibo main > /etc/apt/sources.list.d/dalibo-labs.list curl -fsSL -o /etc/apt/trusted.gpg.d/dalibo-labs.gpg https://apt.dalibo.org/labs/debian-dalibo.gpg && \
    apt-get install -y postgresql_anonymizer_17

# Add the anonymizer extension to the shared preload libraries
RUN echo "shared_preload_libraries = 'anon'" >> /usr/share/postgresql/postgresql.conf.sample

# Set the default command to run PostgreSQL
CMD ["postgres"]
