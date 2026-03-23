"""Configuration management for Zoho ETL app.

Config is stored in ~/.zoho-etl/config.ini (Mac and Windows).
"""

import configparser
from pathlib import Path

CONFIG_DIR = Path.home() / ".zoho-etl"
CONFIG_FILE = CONFIG_DIR / "config.ini"

# Sections and their default values
DEFAULTS = {
    "paths": {
        "working_folder": "",
    },
    "files": {
        "input_quotes": "Export002.csv",
        "input_listino": "Listino09.csv",
        "input_gadget": "Gadget.csv",
        "input_clienti": "Clienti09.csv",
        "output_file": "ImportSO.csv",
    },
    "email": {
        "smtp_host": "",
        "smtp_port": "587",
        "smtp_use_tls": "true",
        "smtp_username": "",
        "smtp_password": "",
        "from_address": "",
        "recipients": "",
        "subject_prefix": "Sales Orders",
    },
}


class AppConfig:
    def __init__(self):
        self._parser = configparser.ConfigParser()
        self._ensure_defaults()

    def _ensure_defaults(self):
        for section, values in DEFAULTS.items():
            if not self._parser.has_section(section):
                self._parser.add_section(section)
            for key, value in values.items():
                if not self._parser.has_option(section, key):
                    self._parser.set(section, key, value)

    def load(self):
        """Load config from disk. Missing file is fine — defaults apply."""
        if CONFIG_FILE.exists():
            self._parser.read(CONFIG_FILE, encoding="utf-8")
        self._ensure_defaults()

    def save(self):
        """Persist config to disk."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            self._parser.write(f)

    # --- Convenience getters/setters ---

    @property
    def working_folder(self) -> str:
        return self._parser.get("paths", "working_folder")

    @working_folder.setter
    def working_folder(self, value: str):
        self._parser.set("paths", "working_folder", value)

    def get_file(self, key: str) -> str:
        return self._parser.get("files", key)

    def set_file(self, key: str, value: str):
        self._parser.set("files", key, value)

    def get_input_path(self, key: str) -> Path:
        return Path(self.working_folder) / self.get_file(key)

    def get_output_path(self) -> Path:
        return Path(self.working_folder) / self.get_file("output_file")

    # Email properties
    @property
    def smtp_host(self) -> str:
        return self._parser.get("email", "smtp_host")

    @smtp_host.setter
    def smtp_host(self, v: str):
        self._parser.set("email", "smtp_host", v)

    @property
    def smtp_port(self) -> int:
        return self._parser.getint("email", "smtp_port")

    @smtp_port.setter
    def smtp_port(self, v: int):
        self._parser.set("email", "smtp_port", str(v))

    @property
    def smtp_use_tls(self) -> bool:
        return self._parser.getboolean("email", "smtp_use_tls")

    @smtp_use_tls.setter
    def smtp_use_tls(self, v: bool):
        self._parser.set("email", "smtp_use_tls", "true" if v else "false")

    @property
    def smtp_username(self) -> str:
        return self._parser.get("email", "smtp_username")

    @smtp_username.setter
    def smtp_username(self, v: str):
        self._parser.set("email", "smtp_username", v)

    @property
    def smtp_password(self) -> str:
        return self._parser.get("email", "smtp_password")

    @smtp_password.setter
    def smtp_password(self, v: str):
        self._parser.set("email", "smtp_password", v)

    @property
    def from_address(self) -> str:
        return self._parser.get("email", "from_address")

    @from_address.setter
    def from_address(self, v: str):
        self._parser.set("email", "from_address", v)

    @property
    def recipients(self) -> list[str]:
        raw = self._parser.get("email", "recipients")
        return [r.strip() for r in raw.split(",") if r.strip()]

    @recipients.setter
    def recipients(self, v: list[str]):
        self._parser.set("email", "recipients", ", ".join(v))

    @property
    def subject_prefix(self) -> str:
        return self._parser.get("email", "subject_prefix")

    @subject_prefix.setter
    def subject_prefix(self, v: str):
        self._parser.set("email", "subject_prefix", v)

    @property
    def email_configured(self) -> bool:
        """True only if enough email settings are present to attempt a send."""
        return bool(self.smtp_host and self.from_address and self.recipients)

    def validate(self) -> list[str]:
        """Return a list of human-readable errors. Empty list = valid."""
        errors = []
        if not self.working_folder:
            errors.append("Working folder is not set.")
        elif not Path(self.working_folder).is_dir():
            errors.append(f"Working folder does not exist: {self.working_folder}")
        return errors

    def needs_setup(self) -> bool:
        """True if the app hasn't been configured at all yet."""
        return not self.working_folder
