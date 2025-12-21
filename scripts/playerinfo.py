'''
Gets a player's info using a geoip database.

Commands
^^^^^^^^

* ``/timezone <player>`` guess player's local time

.. codeauthor:: Liza
'''

import datetime
import os
from zoneinfo import ZoneInfo
from piqueserver.commands import command, target_player
from piqueserver.config import config

try:
    import geoip2.database
    import geoip2.errors
    database = geoip2.database.Reader(os.path.join(
        config.config_dir, 'data/GeoLite2-City.mmdb'))
except ImportError:
    print("(/timezone and /native commands are disabled. Please install geoip2 to enable.)")
except (IOError, OSError):
    print("(/timezone and /native commands are disabled due to missing GeoIP database. Run 'piqueserver --update-geoip' to install.)")


NOTZ = []

try:
    with open(os.path.join(config.config_dir, 'no_tz.txt')) as f:
        NOTZ = f.read().splitlines()
except:
    f = open(os.path.join(config.config_dir, 'no_tz.txt'), 'w')
    f.close()

NONATIVE = []

try:
    with open(os.path.join(config.config_dir, 'no_native.txt')) as f:
        NONATIVE = f.read().splitlines()
except:
    f = open(os.path.join(config.config_dir, 'no_native.txt'), 'w')
    f.close()


@command('timezone', 'tz')
@target_player
def timezone(connection, player):
    """
    Guess player's local time
    /timezone <player>
    """
    if player.name in NOTZ:
        return "%s decided to not show their local time" % player.name
    record = database.city(player.address[0])
    tz_name = record.location.time_zone
    tz_time = datetime.datetime.now().astimezone(ZoneInfo(tz_name))
    return "%s's time is probably %s" % (player.name, tz_time.strftime('%H:%M'))

@command()
def notz(connection):
    """
    Toggle showing your guessed current time with /tz command
    /notz
    """
    if connection.name in NOTZ:
        NOTZ.remove(connection.name)
        connection.send_chat('Your local time is now shown')
    else:
        NOTZ.append(connection.name)
        connection.send_chat('Your local time will no longer be shown')
    with open(os.path.join(config.config_dir, 'no_tz.txt'), 'w') as f:
        f.write('\n'.join(NOTZ))

languages = {
    'AD': 'Catalan',
    'AE': 'Arabic',
    'AF': 'Dari',
    'AG': 'English',
    'AI': 'English',
    'AL': 'Albanian',
    'AM': 'Armenian',
    'AO': 'Portuguese',
    'AR': 'Spanish',
    'AS': 'English',
    'AT': 'German',
    'AU': 'English',
    'AW': 'Dutch',
    'AX': 'Finnish/Swedish',
    'AZ': 'Azerbaijani',
    'BA': 'Serbo-Croatian',
    'BB': 'English',
    'BD': 'Bengali',
    'BE': 'French/Dutch',
    'BE-01': 'Dutch',
    'BE-03': 'French',
    'BE-04': 'French',
    'BE-05': 'Dutch',
    'BE-06': 'French',
    'BE-07': 'French',
    'BE-08': 'Dutch',
    'BE-09': 'Dutch',
    'BE-10': 'French',
    'BE-11': 'French',
    'BE-12': 'Dutch',
    'BE-13': 'Dutch',
    'BE-14': 'French',
    'BF': 'French',
    'BG': 'Bulgarian',
    'BH': 'Arabic',
    'BI': 'French',
    'BJ': 'French',
    'BL': 'French',
    'BM': 'English',
    'BN': 'Malay',
    'BO': 'Spanish/Quechua',
    'BQ': 'Dutch',
    'BR': 'Portuguese',
    'BS': 'English',
    'BT': 'Dzongkha',
    'BW': 'English',
    'BY': 'Russian',
    'BZ': 'English/Spanish',
    'CA': 'English/French',
    'CA-QC': 'French/English',
    'CC': 'English',
    'CD': 'French',
    'CF': 'French',
    'CG': 'French',
    'CH': 'German/French/Italian',
    'CI': 'French',
    'CK': 'English',
    'CL': 'Spanish',
    'CM': 'French/English',
    'CM-07': 'English',
    'CM-09': 'English',
    'CN': 'Mandarin',
    'CO': 'Spanish',
    'CR': 'Spanish',
    'CU': 'Spanish',
    'CV': 'Portuguese',
    'CW': 'Dutch',
    'CX': 'English',
    'CY': 'Greek/Turkish', # Northern Cyprus uses IP ranges assigned to either CY or TR
    'CZ': 'Czech',
    'DE': 'German',
    'DJ': 'Arabic/French',
    'DK': 'Danish',
    'DM': 'French/English',
    'DO': 'Spanish',
    'DZ': 'Arabic',
    'EC': 'Spanish',
    'EE': 'Estonian',
    'EG': 'Arabic',
    'EH': 'Arabic',
    'ER': 'Arabic',
    'ES': 'Spanish',
    'ES-56': 'Catalan',
    'ET': 'Amharic',
    'FI': 'Finnish',
    'FJ': 'English/Hindi',
    'FK': 'English',
    'FM': 'English',
    'FO': 'Faroese',
    'FR': 'French',
    'GA': 'French',
    'GB': 'English',
    'GD': 'French/English',
    'GE': 'Georgian', # Abkhazia uses IP ranges assigned to either GE or RU
    'GF': 'French',
    'GG': 'English',
    'GH': 'English',
    'GI': 'English',
    'GL': 'Danish',
    'GM': 'English',
    'GN': 'French',
    'GP': 'French',
    'GQ': 'Spanish',
    'GR': 'Greek',
    'GT': 'Spanish',
    'GU': 'English',
    'GW': 'Portuguese',
    'GY': 'English',
    'HK': 'Mandarin/Cantonese',
    'HN': 'Spanish',
    'HR': 'Serbo-Croatian',
    'HT': 'French',
    'HU': 'Hungarian',
    'ID': 'Indonesian',
    'ID-04': 'Indonesian/Javanese',
    'ID-07': 'Indonesian/Javanese',
    'ID-08': 'Indonesian/Javanese',
    'ID-10': 'Indonesian/Javanese',
    'ID-30': 'Indonesian/Javanese',
    'ID-33': 'Indonesian/Javanese',
    'IE': 'English/Irish',
    'IL': 'Hebrew/Arabic',
    'IM': 'English',
    'IN': 'Hindi',
    'IN-02': 'Telugu',
    'IN-03': 'Assamese',
    'IN-09': 'Gujarati',
    'IN-13': 'Malayalam',
    'IN-16': 'Marathi',
    'IN-19': 'Kannada',
    'IN-23': 'Punjabi',
    'IN-25': 'Tamil',
    'IN-28': 'Bengali',
    'IN-40': 'Telugu',
    'IO': 'English',
    'IQ': 'Arabic',
    'IQ-05': 'Arabic/Kurdish',
    'IQ-08': 'Arabic/Kurdish',
    'IQ-11': 'Arabic/Kurdish',
    'IR': 'Farsi',
    'IR-01': 'Farsi/Azerbaijani',
    'IR-15': 'Farsi/Arabic',
    'IR-16': 'Farsi/Kurdish',
    'IR-32': 'Farsi/Azerbaijani',
    'IR-33': 'Farsi/Azerbaijani',
    'IS': 'Icelandic',
    'IT': 'Italian',
    'JE': 'English',
    'JM': 'English',
    'JO': 'Arabic',
    'JP': 'Japanese',
    'KE': 'English/Swahili',
    'KG': 'Kyrgyz',
    'KH': 'Khmer',
    'KI': 'English',
    'KM': 'Arabic/French',
    'KN': 'English',
    'KR': 'Korean',
    'KW': 'Arabic',
    'KY': 'English',
    'KZ': 'Kazakh/Russian',
    'LA': 'Lao',
    'LB': 'Arabic',
    'LC': 'French/English',
    'LI': 'German',
    'LK': 'Sinhalese',
    'LR': 'English',
    'LS': 'English',
    'LT': 'Lithuanian',
    'LU': 'German/French',
    'LV': 'Latvian',
    'LY': 'Arabic',
    'MA': 'Arabic',
    'MC': 'French',
    'MD': 'Romanian/Russian',
    'ME': 'Serbo-Croatian',
    'MF': 'French',
    'MG': 'French',
    'MH': 'English',
    'MK': 'Macedonian',
    'ML': 'French',
    'MM': 'Burmese',
    'MN': 'Mongolian',
    'MO': 'Mandarin/Cantonese',
    'MP': 'English',
    'MQ': 'French',
    'MR': 'Arabic',
    'MS': 'English',
    'MT': 'Maltese',
    'MU': 'French/English',
    'MV': 'Dhivehi',
    'MW': 'English',
    'MX': 'Spanish',
    'MY': 'Malay',
    'MZ': 'Portuguese',
    'NA': 'English',
    'NC': 'French',
    'NE': 'French',
    'NF': 'English',
    'NG': 'English',
    'NI': 'Spanish',
    'NL': 'Dutch',
    'NO': 'Norwegian',
    'NP': 'Nepali',
    'NR': 'English',
    'NU': 'English',
    'NZ': 'English',
    'OM': 'Arabic',
    'PA': 'Spanish',
    'PE': 'Spanish',
    'PF': 'French',
    'PG': 'English',
    'PH': 'Filipino',
    'PK': 'Urdu',
    'PL': 'Polish',
    'PM': 'French',
    'PR': 'English/Spanish',
    'PS': 'Arabic',
    'PT': 'Portuguese',
    'PW': 'English',
    'PY': 'Spanish/Guarani',
    'QA': 'Arabic',
    'RE': 'French',
    'RO': 'Romanian',
    'RS': 'Serbo-Croatian',
    'RU': 'Russian',
    'RW': 'French',
    'SA': 'Arabic',
    'SB': 'English',
    'SC': 'French/English',
    'SD': 'Arabic',
    'SE': 'Swedish',
    'SG': 'Singlish',
    'SH': 'English',
    'SI': 'Slovenian',
    'SK': 'Slovak',
    'SL': 'English',
    'SM': 'Italian',
    'SN': 'French',
    'SO': 'Somali',
    'SR': 'Dutch',
    'SS': 'English',
    'ST': 'Portuguese',
    'SV': 'Spanish',
    'SX': 'Dutch',
    'SY': 'Arabic',
    'SZ': 'English',
    'TC': 'English',
    'TD': 'Arabic/French',
    'TG': 'French',
    'TH': 'Thai',
    'TJ': 'Tajik',
    'TK': 'English',
    'TL': 'Portuguese',
    'TM': 'Turkmen',
    'TN': 'Arabic',
    'TO': 'English',
    'TR': 'Turkish',
    'TT': 'English',
    'TV': 'English',
    'TW': 'Mandarin/Hokkien',
    'TZ': 'English/Swahili',
    'UA': 'Ukrainian/Russian',
    'UA-11': 'Russian', # Crimea
    'UA-20': 'Russian', # Sevastopol
    # Other Russian-controlled areas use IP ranges assigned to RU,
    # e.g. Russian-controlled parts of Donetsk use Rostov region ranges
    'UG': 'English',
    'US': 'English',
    'UY': 'Spanish',
    'UZ': 'Uzbek',
    'VC': 'English',
    'VE': 'Spanish',
    'VG': 'English',
    'VI': 'English',
    'VN': 'Vietnamese',
    'VU': 'French/English',
    'WF': 'French',
    'WS': 'English',
    'XK': 'Albanian',
    'YE': 'Arabic',
    'YT': 'French',
    'ZA': 'English',
    'ZM': 'English',
    'ZW': 'English',
    }

@command()
@target_player
def native(connection, player):
    """
    Guess language a player might speak
    /native <player>
    """
    if player.name in NONATIVE:
        return "%s decided to not show their language" % player.name

    record = database.city(player.address[0])
    country_code = record.country.iso_code

    try:
        adm1_code = record.subdivisions[0].iso_code
    except:
        adm1_code = None

    if adm1_code:
        code = country_code + '-' + adm1_code
    else:
        code = country_code

    if code in languages:
        return "%s's language might be %s" % (player.name, languages[code])
    elif country_code in languages:
        return "%s's language might be %s" % (player.name, languages[country_code])
    else:
        return "%s's language is unknown" % player.name

@command()
def nonative(connection):
    """
    Toggle showing your guessed language with /native command
    /nonative
    """
    if connection.name in NONATIVE:
        NONATIVE.remove(connection.name)
        connection.send_chat('Your language is now shown')
    else:
        NONATIVE.append(connection.name)
        connection.send_chat('Your language will no longer be shown')
    with open(os.path.join(config.config_dir, 'no_native.txt'), 'w') as f:
        f.write('\n'.join(NONATIVE))


def apply_script(protocol, connection, config):
    return protocol, connection
