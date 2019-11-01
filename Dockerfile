FROM docker.io/python:3-alpine

WORKDIR /usr/src/app
COPY requirements.txt /usr/src/app/requirements.txt

RUN apk add --no-cache gcc g++ mariadb-dev mariadb-connector-c musl-dev libffi libffi-dev mariadb-client openssl \
    && pip install --no-cache-dir -r requirements.txt \
    && apk del gcc g++ mariadb-dev musl-dev libffi-dev \
    && adduser -S exporter


COPY prometheus_mysql_exporter/*.py /usr/src/app/prometheus_mysql_exporter/
COPY setup.py /usr/src/app/
COPY LICENSE /usr/src/app/
COPY README.md /usr/src/app/
COPY MANIFEST.in /usr/src/app/

RUN pip install -e .

EXPOSE 9207

USER exporter

ENTRYPOINT ["python", "-u", "/usr/local/bin/prometheus-mysql-exporter"]
