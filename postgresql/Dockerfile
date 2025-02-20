FROM postgres:latest

# Install prerequisites
RUN apt-get update

# Add Dalibo Labs APT repository
RUN echo "deb [arch=amd64] http://apt.dalibo.org/labs/$(lsb_release -cs) $(lsb_release -cs)-dalibo main" > /etc/apt/sources.list.d/dalibo-labs.list && \
    curl -fsSL -o /etc/apt/trusted.gpg.d/dalibo-labs.gpg https://apt.dalibo.org/labs/debian-dalibo.gpg && \
    apt-get install -y postgresql_anonymizer_17 && \
    apt-get update

# Set the default command to run PostgreSQL
CMD ["postgres"]