import click
import click_config_file
import configparser
import glob
import logging
import os
import pymysql
import sched

from DBUtils.PersistentDB import PersistentDB
from jog import JogFormatter
from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY

from .metrics import gauge_generator, group_metrics, merge_metric_dicts
from .parser import parse_response
from .scheduler import schedule_job
from .utils import log_exceptions, nice_shutdown

log = logging.getLogger(__name__)

CONTEXT_SETTINGS = {
    'help_option_names': ['-h', '--help']
}

METRICS_BY_QUERY = {}


class QueryMetricCollector(object):

    def collect(self):
        # Copy METRICS_BY_QUERY before iterating over it
        # as it may be updated by other threads.
        # (only first level - lower levels are replaced
        # wholesale, so don't worry about them)
        query_metrics = METRICS_BY_QUERY.copy()
        for metric_dict in query_metrics.values():
            yield from gauge_generator(metric_dict)


def run_query(mysql_client, query_name, db_name, query, value_columns,
              on_error, on_missing):

    log.debug('running query: %s', query_name)
    try:
        conn = mysql_client.connection()

        try:
            with conn.cursor() as cursor:
                cursor.execute('USE `{}`;'.format(db_name))
                cursor.execute(query)
                raw_response = cursor.fetchall()
                columns = [column[0] for column in cursor.description]

        finally:
            conn.close()

        response = [{column: row[i] for i, column in enumerate(columns)}
                    for row in raw_response]
        metrics = parse_response(query_name, db_name, value_columns, response)
        metric_dict = group_metrics(metrics)

    except Exception:
        log.exception('Error while querying db %(db_name)s, query %(query)s.',
                      {'db_name': db_name, 'query': query})

        # If this query has successfully run before, we need to handle any
        # metrics produced by that previous run.
        if query_name in METRICS_BY_QUERY:
            old_metric_dict = METRICS_BY_QUERY[query_name]

            if on_error == 'preserve':
                metric_dict = old_metric_dict

            elif on_error == 'drop':
                metric_dict = {}

            elif on_error == 'zero':
                # Merging the old metric dict with an empty one, and zeroing
                # any missing metrics, produces a metric dict with the same
                # metrics, but all zero values.
                metric_dict = merge_metric_dicts(old_metric_dict, {},
                                                 zero_missing=True)

            METRICS_BY_QUERY[query_name] = metric_dict

    else:
        # If this query has successfully run before, we need to handle any
        # missing metrics.
        if query_name in METRICS_BY_QUERY:
            old_metric_dict = METRICS_BY_QUERY[query_name]

            if on_missing == 'preserve':
                metric_dict = merge_metric_dicts(old_metric_dict, metric_dict,
                                                 zero_missing=False)

            elif on_missing == 'drop':
                pass  # use new metric dict untouched

            elif on_missing == 'zero':
                metric_dict = merge_metric_dicts(old_metric_dict, metric_dict,
                                                 zero_missing=True)

        METRICS_BY_QUERY[query_name] = metric_dict


def validate_server_address(ctx, param, address_string):
    if ':' in address_string:
        host, port_string = address_string.split(':', 1)
        try:
            port = int(port_string)
        except ValueError:
            msg = "port '{}' in address '{}' is not an integer".format(port_string, address_string)
            raise click.BadParameter(msg)
        return (host, port)
    else:
        return (address_string, 3306)


def configparser_enum_conv(enum):
    lower_enums = tuple(e.lower() for e in enum)

    def conv(value):
        lower_value = value.lower()
        if lower_value in lower_enums:
            return lower_value
        else:
            raise ValueError('Value {} not value. Must be one of {}'.format(
                             value, ','.join(enum)))

    return conv


CONFIGPARSER_CONVERTERS = {
    'enum': configparser_enum_conv(('preserve', 'drop', 'zero'))
}


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('--port', '-p', default=9207,
              help='Port to serve the metrics endpoint on. (default: 9207)')
@click.option('--config-file', '-c', default='exporter.cfg', type=click.File(),
              help='Path to query config file. '
                   'Can be absolute, or relative to the current working directory. '
                   '(default: exporter.cfg)')
@click.option('--config-dir', default='./config', type=click.Path(file_okay=False),
              help='Path to query config directory. '
                   'If present, any files ending in ".cfg" in the directory '
                   'will be parsed as additional query config files. '
                   'Merge order is main config file, then config directory files '
                   'in filename order. '
                   'Can be absolute, or relative to the current working directory. '
                   '(default: ./config)')
@click.option('--mysql-server', '-s', callback=validate_server_address, default='localhost',
              help='Address of a MySQL server to run queries on. '
                   'A port can be provided if non-standard (3306) e.g. mysql:3333. '
                   '(default: localhost)')
@click.option('--mysql-user', '-u', default='root',
              help='MySQL user to run queries as. (default: root)')
@click.option('--mysql-password', '-P', default='',
              help='Password for the MySQL user, if required. (default: no password)')
@click.option('--mysql-local-timezone', '-z',
              help='Local timezone for sql commands like NOW(). (default: use server timezone)')
@click.option('--json-logging', '-j', default=False, is_flag=True,
              help='Turn on json logging.')
@click.option('--log-level', default='INFO',
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']),
              help='Detail level to log. (default: INFO)')
@click.option('--verbose', '-v', default=False, is_flag=True,
              help='Turn on verbose (DEBUG) logging. Overrides --log-level.')
@click_config_file.configuration_option()
def cli(**options):
    """Export MySQL query results to Prometheus."""

    log_handler = logging.StreamHandler()
    log_format = '[%(asctime)s] %(name)s.%(levelname)s %(threadName)s %(message)s'
    formatter = JogFormatter(log_format) if options['json_logging'] else logging.Formatter(log_format)
    log_handler.setFormatter(formatter)

    log_level = getattr(logging, options['log_level'])
    logging.basicConfig(
        handlers=[log_handler],
        level=logging.DEBUG if options['verbose'] else log_level
    )
    logging.captureWarnings(True)

    port = options['port']
    mysql_host, mysql_port = options['mysql_server']

    username = options['mysql_user']
    password = options['mysql_password']
    timezone = options['mysql_local_timezone']

    config = configparser.ConfigParser(converters=CONFIGPARSER_CONVERTERS)
    config.read_file(options['config_file'])

    config_dir_file_pattern = os.path.join(options['config_dir'], '*.cfg')
    config_dir_sorted_files = sorted(glob.glob(config_dir_file_pattern))
    config.read(config_dir_sorted_files)

    query_prefix = 'query_'
    queries = {}
    for section in config.sections():
        if section.startswith(query_prefix):
            query_name = section[len(query_prefix):]
            interval = config.getfloat(section, 'QueryIntervalSecs',
                                       fallback=15)
            cron = config.get(section, 'QueryCronString', fallback=None)
            db_name = config.get(section, 'QueryDatabase')
            query = config.get(section, 'QueryStatement')
            value_columns = config.get(section, 'QueryValueColumns').split(',')
            on_error = config.getenum(section, 'QueryOnError',
                                      fallback='drop')
            on_missing = config.getenum(section, 'QueryOnMissing',
                                        fallback='drop')

            queries[query_name] = (interval, db_name, query, value_columns,
                                   on_error, on_missing, cron)

    scheduler = sched.scheduler()

    mysql_kwargs = dict(host=mysql_host,
                        port=mysql_port,
                        user=username,
                        password=password,
                        # Use autocommit mode to avoid keeping the same transaction across query
                        # runs when the connection is reused. Using the same transaction would
                        # prevent changes from being reflected in results, and therefore metrics.
                        # Note: Queries could theoretically change data...
                        autocommit=True)
    if timezone:
        mysql_kwargs['init_command'] = "SET time_zone = '{}'".format(timezone)
    else:
        timezone = None

    mysql_client = PersistentDB(creator=pymysql, **mysql_kwargs)

    if queries:
        for query_name, (interval, db_name, query, value_columns,
                         on_error, on_missing, cron) in queries.items():
            schedule_job(scheduler, interval, cron, timezone,
                         run_query, mysql_client, query_name,
                         db_name, query, value_columns, on_error, on_missing)
    else:
        log.warning('No queries found in config file(s)')

    REGISTRY.register(QueryMetricCollector())

    log.info('Starting server...')
    start_http_server(port)
    log.info('Server started on port %(port)s', {'port': port})

    scheduler.run()


@log_exceptions(exit_on_exception=True)
@nice_shutdown()
def main():
    cli(auto_envvar_prefix='MYSQL_EXPORTER')
