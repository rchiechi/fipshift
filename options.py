'''Parse command line args and config files'''
import os
import argparse
import configparser
import shutil


def parseopts():
    '''Parse commandline arguments and config file and return opts, config'''

    desc = '''Create an shoutcast client that time-shifts
            FIP for listening in a different timezone.'''
    parser = argparse.ArgumentParser(description=desc,
                                     formatter_class=argparse
                                     .ArgumentDefaultsHelpFormatter)

    parser.add_argument('-d', '--delay', action=StoreHours, default=21600,
                        type=int,
                        help="Delay time in hours.")

    parser.add_argument('-r', '--restart', action=StoreHours, default=0,
                        type=int,
                        help="Restart every n hours (0 means do not restart).")

    parser.add_argument('--ezstream', action="store", default='',
                        type=str,
                        help="Path to ezstream if not in PATH.")

    parser.add_argument('--ffmpeg', action="store", default='',
                        type=str,
                        help="Path to ffmpeg if not in PATH.")

    parser.add_argument('--configdir', action="store",
                        default=os.path.join(os.path.expanduser('~'), '.config'),
                        help="Set the dir to look for the config file.")

    opts = parser.parse_args()
    config = doconfig(os.path.join(opts.configdir,
                      'fipshift.conf')
                      )
    return opts, config


def doconfig(config_file):
    '''Parse config file or write a default file.'''
    if not os.path.exists(config_file):
        _pwd = os.path.dirname(os.path.realpath(__file__))
        shutil.copy2(os.path.join(_pwd,'template.conf'), config_file)
        return doconfig(config_file)
    config = configparser.ConfigParser(allow_no_value=False)
    config.read(config_file)
    if 'USEROPTS' not in config or 'ICES' not in config:
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
            setattr(namespace, self.dest, 3600*values)
        # setattr(namespace, self.dest, values)