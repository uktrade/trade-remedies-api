FROM python:3.7

RUN apt-get update && apt-get install -y wget

WORKDIR /opt/traderemedies/api
ADD . /opt/traderemedies/api
VOLUME ["/opt/traderemedies/api"]

# Run pip to install all requirements
RUN \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements-dev.txt

# Install dockerize https://github.com/jwilder/dockerize
ENV DOCKERIZE_VERSION v0.6.1
RUN wget -q https://github.com/jwilder/dockerize/releases/download/$DOCKERIZE_VERSION/dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && tar -C /usr/local/bin -xzvf dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz

EXPOSE 8000

ENTRYPOINT ["./bootstrap.sh"]
