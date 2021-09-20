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

    parser.add_argument('-d','--delay', action="store", default=9*3600,
                        type=int,
                        help="Delay time in seconds.")

    parser.add_argument('--configdir', action="store",
                        default=os.path.join(os.path.expanduser('~'),'.config'),
                        help="Set the dir to look for the config file.")

    opts = parser.parse_args()
    config = doconfig(os.path.join(opts.configdir,
                      'fipshift.conf')
                      )
    return opts,config

def doconfig(config_file):
    '''Parse config file or write a default file.'''
    if not os.path.exists(config_file):
        _pwd = os.path.dirname(os.path.realpath(__file__))
        shutil.copy2(os.path.join(_pwd,'template.conf'), config_file)
        return None
    config = configparser.ConfigParser(allow_no_value=False)
    config.read(config_file)
    if 'USEROPTS' not in config or 'ICES' not in config:
        config = configparser.ConfigParser(allow_no_value=False)
        config.read(os.path.basename(config_file))
    return config
