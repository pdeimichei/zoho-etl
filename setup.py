from setuptools import setup

APP = ['src/main.py']
DATA_FILES = [('', ['config.ini.example'])]
OPTIONS = {
    'argv_emulation': False,
    'packages': ['pandas', 'openpyxl', 'numpy', 'tkinter'],
    'includes': ['csv', 're', 'configparser', 'smtplib', 'email', 'threading', 'queue'],
    'plist': {
        'CFBundleName': 'ZohoETL',
        'CFBundleDisplayName': 'Zoho ETL',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
    },
    'extra_scripts': ['src/config.py', 'src/email_sender.py'],
}

setup(
    name='ZohoETL',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
