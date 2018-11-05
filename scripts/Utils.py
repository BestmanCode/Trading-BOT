# Utility functions are stored in this class and accessed as static members

import logging
import json
from enum import Enum

class TradeDirection(Enum):
    NONE = "NONE",
    BUY = "BUY",
    SELL = "SELL"

class Utils:
    def __init__(self):
        pass

    @staticmethod
    def midpoint(p1, p2):
        """Return the midpoint"""
        return (p1 + p2) / 2

    @staticmethod
    def percentage_of(percent, whole):
        """Return the value of the percentage on the whole"""
        return (percent * whole) / 100.0

    @staticmethod
    def percentage(part, whole):
        """Return the percentage value of the part on the whole"""
        return 100 * float(part) / float(whole)

    @staticmethod
    def is_between(time, time_range):
        """Return True if time is between the time_range. time must be a datetime obj.
        time_range must be a tuple (a,b) where a and b are strings in format 'HH:MM'"""
        if time_range[1] < time_range[0]:
            return time >= time_range[0] or time <= time_range[1]
        return time_range[0] <= time <= time_range[1]

    @staticmethod
    def humanize_time(secs):
        """Convert the given time (in seconds) into a readable format hh:mm:ss"""
        mins, secs = divmod(secs, 60)
        hours, mins = divmod(mins, 60)
        return '%02d:%02d:%02d' % (hours, mins, secs)
