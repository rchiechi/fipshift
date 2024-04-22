'''Parse command line args and config files'''
import os
import datetime
import argparse
import configparser
import shutil
import zoneinfo


def parseopts():
    '''Parse command line arguments and config file and return opts, config'''

    desc = '''Create an shoutcast client that time-shifts
            FIP for listening in a different timezone.'''
    parser = argparse.ArgumentParser(description=desc,
                                     formatter_class=argparse
                                     .ArgumentDefaultsHelpFormatter)

    parser.add_argument('-z', '--timezone', action=StoreDelay, default="America/New_York",
                        type=str,
                        help="Local timezone.")

    # parser.add_argument('-d', '--delay', action=StoreHours, default=21600,
    #                     type=int,
    #                     help="Delay time in hours defaults to difference between local and CET.")

    parser.add_argument('--ffmpeg', action="store", default='',
                        type=str,
                        help="Path to ffmpeg if not in PATH.")

    parser.add_argument('--configdir', action="store",
                        default=os.path.join(os.path.expanduser('~'), '.config'),
                        help="Set the dir to look for the config file.")

    parser.add_argument('--debug', action="store_true",
                        default=False,
                        help="Turn on debug logging.")

    opts = parser.parse_args()
    if not hasattr(opts, 'delay'):
        setattr(opts, 'delay', 21600)
    config = doconfig(os.path.join(opts.configdir, 'fipshift.conf'))
    return opts, config

class StoreDelay(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
        try:
            here = datetime.datetime(1979, 1, 1, 0, tzinfo=zoneinfo.ZoneInfo(values))
            there = datetime.datetime(1979, 1, 1, 0, tzinfo=zoneinfo.ZoneInfo('Europe/Paris'))
            setattr(namespace, 'delay', (here - there).seconds)
        except zoneinfo.ZoneInfoNotFoundError:
            print(f"Invalid timezone: {values}")
            setattr(namespace, 'delay', 120)  # for debugging

def doconfig(config_file):
    '''Parse config file or write a default file.'''
    if not os.path.exists(config_file):
        _pwd = os.path.dirname(os.path.realpath(__file__))
        shutil.copy2(os.path.join(os.path.join(_pwd, '..'), 'template.conf'), config_file)
        return doconfig(config_file)
    config = configparser.ConfigParser(allow_no_value=False)
    config.read(config_file)
    if 'USEROPTS' not in config:
        config = configparser.ConfigParser(allow_no_value=False)
        config.read(os.path.basename(config_file))
    return config


class StoreHours(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        # print('%r %r %r' % (namespace, values, option_string))
        if values < 0:
            setattr(namespace, self.dest, 120)  # for debugging
        else:
            setattr(namespace, self.dest, 3600 * values)
