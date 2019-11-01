Prometheus MySQL Exporter
====
This Prometheus exporter periodically runs configured queries against a MySQL database and exports the results as Prometheus gauge metrics.

# Installation
The exporter requires Python 3, Pip 3 and libmysqlclient-dev to be installed.

To install the latest published version via Pip, run:
```
> pip3 install prometheus-mysql-exporter
```
Note that you may need to add the start script location (see pip output) to your `PATH`.

# Usage
Once installed, you can run the exporter with the `prometheus-mysql-exporter` command.

By default, it will bind to port 9207, query MySQL on `localhost:3306` using the `root` user (with no password) and run queries configured in a file `exporter.cfg` in the working directory. There is no default database to run the queries on, so you must specify at least one. You can set the database(s) and change any defaults as required by passing in options:
```
> prometheus-mysql-exporter -p <port> -s <mysql server> -u <mysql username> -P <mysql password> -c <path to query config file> -d <mysql database(s)>
```
Run with the `-h` flag to see details on all the available options.

See the provided `exporter.cfg` file for query configuration examples and explanation.

# Docker
Docker images for released versions can be found on Docker Hub (note that no `latest` version is provided):
```
> sudo docker pull braedon/prometheus-mysql-exporter:<version>
```
To run a container successfully, you will need to mount a query config file to `/usr/src/app/exporter.cfg` and map container port 9207 to a port on the host. Any options placed after the image name (`prometheus-mysql-exporter`) will be passed to the process inside the container. For example, you will need to use this to configure the MySQL server using `-s`.
```
> sudo docker run --rm --name exporter \
    -v <path to query config file>:/usr/src/app/exporter.cfg \
    -p <host port>:9207 \
    braedon/prometheus-mysql-exporter:<version> -s <mysql server> -d <mysql database(s)>
```
If you don't want to mount the query config file in at run time, you could extend an existing image with your own Dockerfile that copies the config file in at build time.

The password can also be provided as an environment variable named
`MYSQL_PASSWORD` so that it can be sourced from secrets.

# Development
To install directly from the git repo, run the following in the root project directory:
```
> pip3 install .
```
The exporter can be installed in "editable" mode, using pip's `-e` flag. This allows you to test out changes without having to re-install.
```
> pip3 install -e .
```
To build a docker image directly from the git repo, run the following in the root project directory:
```
> sudo docker build -t <your repository name and tag> .
```
Send me a PR if you have a change you want to contribute!
