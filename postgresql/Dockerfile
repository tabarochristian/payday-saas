FROM postgres:latest

# Install necessary packages
RUN apt-get update && \
    apt-get install -y postgresql_anonymizer_17

# Add the anonymizer extension to the shared preload libraries
RUN echo "shared_preload_libraries = 'anon'" >> /usr/share/postgresql/postgresql.conf.sample

# Set the default command to run PostgreSQL
CMD ["postgres"]
