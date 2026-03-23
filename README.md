# Zoho ETL

Desktop app that transforms Zoho CRM quote exports into a Zoho Inventory import file and emails an order summary to colleagues.

## What it does

1. **Reads** 4 CSV input files from a configured working folder
2. **Transforms** the data (price list merge, quantity/discount/tax calculations)
3. **Writes** `ImportSO.csv` — ready for manual upload to Zoho Inventory
4. **Emails** a plain-text order summary to up to 4 recipients via corporate SMTP

## Input files (place in working folder)

| File | Description | Changes |
|---|---|---|
| `Export002.csv` | Quote export from Zoho CRM | Every run |
| `Listino09.csv` | Product prices per client | Rarely |
| `Gadget.csv` | FOC / gadget items | Rarely |
| `Clienti09.csv` | Customer master (payment terms, VAT) | Rarely |

## Setup (development / running from source)

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python src/main.py
```

On first launch the Settings dialog opens automatically. Fill in:
- **Working folder** — where your CSV files live
- **SMTP settings** — your corporate mail server
- **Recipients** — the 4 colleagues to email

Config is saved to `~/.zoho-etl/config.ini` (never in the project folder).

## Building a standalone executable

Install dev dependencies first:

```bash
pip install -r requirements-dev.txt
```

**Mac:**
```bash
pyinstaller build.spec
# Output: dist/ZohoETL.app
```

**Windows:**
```bash
pyinstaller build.spec
# Output: dist/ZohoETL.exe
```

Distribute the `.app` (zip it) or `.exe` — no Python installation needed on the target machine.

## Versioning

- Version number is set in `src/main.py` → `APP_VERSION`
- Tag releases: `git tag v1.0.0 && git push --tags`
- GitHub Actions (`.github/workflows/build.yml`) automatically builds executables when a `v*.*.*` tag is pushed and attaches them to a GitHub Release

## Project structure

```
zoho-etl/
├── src/
│   ├── main.py                      # GUI entry point
│   ├── config.py                    # Settings management
│   ├── email_sender.py              # SMTP email
│   └── transform/
│       ├── listino_builder.py       # Stage 1: build price list
│       └── quote_processor.py       # Stage 2: process quotes → ImportSO.csv
├── config.ini.example               # Config template (commit this)
├── requirements.txt
├── requirements-dev.txt
├── build.spec                       # PyInstaller build config
└── .gitignore
```

## GitHub workflow

- `main` branch = stable, always runnable
- Create a feature branch for changes, open a PR, merge when ready
- Never commit `config.ini` — it contains credentials
