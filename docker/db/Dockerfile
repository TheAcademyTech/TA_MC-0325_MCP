FROM postgres:15

# Define build argument
ARG POSTGRES_DB
ARG POSTGRES_USER
ARG POSTGRES_PASSWORD

# Set environment variables
ENV POSTGRES_DB=${POSTGRES_DB}
ENV POSTGRES_USER=${POSTGRES_USER}
ENV POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

# Create directory for data
RUN mkdir -p /docker-entrypoint-initdb.d/data

# Copy initialization script and data
COPY db/init/init.sql /docker-entrypoint-initdb.d/
COPY db/init/data/learning_dataset.csv /docker-entrypoint-initdb.d/data/

# Set permissions for the CSV file
RUN chmod 644 /docker-entrypoint-initdb.d/data/learning_dataset.csv

# Expose the PostgreSQL port
EXPOSE 5432 