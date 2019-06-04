"""Utility functions."""

import datetime
import pytz


_TZ_ABBREVIATIONS = {}

for t in pytz.all_timezones:
    tz = pytz.timezone(t)
    abbrev = tz.tzname(datetime.datetime(2019, 1, 1))

    _TZ_ABBREVIATIONS[abbrev] = tz


def get_tzinfo_from_abbreviation(abbrev):
    """Get a tzinfo object from a timezone abbreviation."""
    return _TZ_ABBREVIATIONS.get(abbrev, None)
