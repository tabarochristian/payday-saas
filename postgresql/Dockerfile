FROM postgres:latest

# Step 1: Install prerequisites
RUN apt-get update && \
    apt-get install -y curl lsb-release

# Step 2: Add Dalibo Labs APT repository
RUN echo "deb [arch=amd64] http://apt.dalibo.org/labs/$(lsb_release -cs) $(lsb_release -cs)-dalibo main" > /etc/apt/sources.list.d/dalibo-labs.list && \
    curl -fsSL -o /etc/apt/trusted.gpg.d/dalibo-labs.gpg https://apt.dalibo.org/labs/debian-dalibo.gpg

# Step 3: Install PostgreSQL Anonymizer
RUN apt-get update && \
    apt-get install -y postgresql-anonymizer-17

# Step 4: Add the anonymizer extension to the shared preload libraries
RUN echo "shared_preload_libraries = 'anon'" >> /usr/share/postgresql/postgresql.conf.sample

# Step 5: Set the default command to run PostgreSQL
CMD ["postgres"]