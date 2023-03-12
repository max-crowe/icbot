from pathlib import Path


TIME_ZONE = "America/Chicago"
POLICE_LOG_URL = "https://www.iowa-city.org/IcgovApps/police/ActivityLog"
POLICE_LOG_DATETIME_FORMAT = "%-m/%-d/%Y"
BLOCKING_FILTERS = {
    "ACTIVITIES": [
        "MVA/PROPERTY DAMAGE ACCIDENT",
        "911 HANGUP",
        "SUICIDE/LAW",
        "TR/PARKING",
        "ESCORT/RELAY",
        "ALARM/PANIC/HOLDUP",
        "MENTAL IMPAIRMENT",
        "TRAFFIC STOP",
        "MISSING/JUVENILE",
        "WELFARE CHECK",
        "PAPER SERVICE/WARRANT",
        "^Z",
        "^TEST"
    ],
    "DISPOSITIONS": [
        "(EMPL ERROR|UNK CAUSE) ALARM",
    ],
    "DETAILS": [
        "CREATED FROM MOBILE",
        "CFS",
        "MILEAGE REPORT",
        "OLN/",
        "SOC/",
        "DOB/",
        "^EVE?NT",
        "^REF AMB",
        "^REQ CERT",
        "^FRONT DESK RELIEF",
        "^TYPE OF CALL CHANGED",
        "^SCHEDULED FOR",
        "^\*+PRIVATE"
    ]
}
LOGGING = {
    "version": 1,
    "formatters": {
        "detailed": {
            "class": "logging.Formatter",
            "format": "%(asctime)s: [%(pathname)s:%(levelname)s]: %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "detailed"
        }
    },
    "root": {
        "level": "DEBUG",
        "handlers": ["console"]
    }
}
DATA_DIR = Path(__file__).parent.parent.parent / "data"
# STORAGE should be a dict containing the keys "class" and "init_kwargs",
# e.g.:
#
# STORAGE = {
#     "class": "storage.GoogleSheetsStorage",
#     "init_kwargs": {
#         "spreadsheet_id": "foo",
#         "client_secrets_file": "/path/to/file.json"
#     }
# }
STORAGE = None

EMAIL_FROM_ADDRESS = "icbot@localhost"
SMTP_HOST = None
SMTP_PORT = 0
SMTP_USERNAME = None
SMTP_PASSWORD = None
