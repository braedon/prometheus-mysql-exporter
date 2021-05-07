import time
from math import ceil
import logging
import pytz
from croniter import croniter
from datetime import datetime

log = logging.getLogger(__name__)


def schedule_job(scheduler, interval, cron, timezone, func, *args, **kwargs):
    """
    Schedule a function to be run on a fixed interval
    or cron-based (croniter)

    Works with schedulers from the stdlib sched module.
    """

    def scheduled_run(scheduled_time, *args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception:
            log.exception('Error while running scheduled job.')

        current_time = time.monotonic()
        if cron:
            next_scheduled_time = scheduled_time + cron_interval(cron, timezone)
            log.debug('next cron based run at: %s seconds from now', ceil(next_scheduled_time - current_time))
        else:
            next_scheduled_time = scheduled_time + interval
            while next_scheduled_time < current_time:
                next_scheduled_time += interval
            log.debug('next interval based run at: %s seconds from now', ceil(next_scheduled_time - current_time))

        scheduler.enterabs(time=next_scheduled_time,
                           priority=1,
                           action=scheduled_run,
                           argument=(next_scheduled_time, *args),
                           kwargs=kwargs)

    next_scheduled_time = time.monotonic()
    scheduler.enterabs(time=next_scheduled_time,
                       priority=1,
                       action=scheduled_run,
                       argument=(next_scheduled_time, *args),
                       kwargs=kwargs)

def cron_interval(cronstring, timezone):
    """
    Return seconds until the next cron run time by parsing
    a cron string. Uses the croniter module
    """
    if timezone:
        tz = pytz.timezone(timezone)
        local_date = tz.localize(datetime.now())
    else:
        local_date = datetime.now().astimezone()
    interval = 0
    crony = croniter(cronstring, local_date)
    while interval < 1:
        next_dt = crony.get_next(datetime)
        interval = (next_dt - local_date).total_seconds()
    log.debug('cron_tick: %s', ceil(interval))
    return ceil(interval)
