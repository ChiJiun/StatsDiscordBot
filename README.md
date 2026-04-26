# Discord Statistics FRQ Grading Bot

This project is a Discord-based grading bot for statistics FRQ submissions. Students log in with their student ID and password, upload HTML answer files in their class channel, and receive AI-assisted feedback on both English expression and statistical content. The system also keeps submission history, stores generated reports, and organizes files in Google Drive.

The current implementation is a long-running Python bot, not a web app. Its main workflow is:

1. Students authenticate in Discord with `!login student_id password`
2. The bot maps the student to the correct class role and channel
3. Students upload HTML FRQ response files
4. The bot parses the HTML title, student info, and answer content
5. OpenAI generates English and statistics feedback based on question-specific prompts
6. The system generates an HTML report, saves submission records in SQLite, and uploads files to Google Drive

## Features

- Discord login and class-role assignment
- Multi-class channel support
- AI-assisted grading for English and statistics
- Question-specific prompt mapping
- Submission history and attempt tracking
- HTML grading report generation
- SQLite-based student and submission records
- Google Drive upload for submission files and reports
- Admin tools for welcome messages, score export, and system open/close control

## Project Structure

```text
Bot/
├── main.py                    # Entry point
├── discord_bot.py             # Main Discord bot logic
├── config.py                  # Environment loading and project configuration
├── database.py                # SQLite database operations
├── grading.py                 # OpenAI grading service
├── html_parser.py             # HTML parsing utilities
├── file_handler.py            # Local file storage + Google Drive upload
├── report_generator.py        # HTML report generation
├── requirements.txt           # Python dependencies
├── .env.example               # Example environment variables
├── homework.db                # SQLite database file
├── prompts/                   # English/statistics grading prompts
├── Question/                  # Question source files
├── Answer/                    # Reference answer files
├── Course List/               # Excel rosters
├── uploads/                   # Saved student submissions
├── reports/                   # Generated HTML reports
└── script/
    ├── oauth_setup.py         # Google Drive OAuth setup
    └── student_importer.py    # Import student rosters from Excel
```

## Requirements

- Python 3.10+ recommended
- A Discord bot token
- An OpenAI API key
- A Google Cloud OAuth client for Google Drive upload
- Access to the target Discord server, channels, and roles

## Installation

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

If you are using macOS or Linux:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root. You can copy from `.env.example` and fill in the real values.

Required environment variables:

```env
DISCORD_TOKEN=your_discord_bot_token
OPENAI_API_KEY=your_openai_api_key

UPLOADS_FOLDER_ID=your_google_drive_uploads_folder_id
REPORTS_FOLDER_ID=your_google_drive_reports_folder_id

WELCOME_CHANNEL_ID=your_welcome_channel_id
NCUFN_CHANNEL_ID=your_ncufn_channel_id
NCUEC_CHANNEL_ID=your_ncuec_channel_id
CYCUIUBM_CHANNEL_ID=your_cycuiubm_channel_id
HWIS_CHANNEL_ID=your_hwis_channel_id

ADMIN_CHANNEL_ID=your_admin_channel_id
ADMIN_ROLE_ID=your_admin_role_id

NCUFN_ROLE_ID=optional_role_id
NCUEC_ROLE_ID=optional_role_id
CYCUIUBM_ROLE_ID=optional_role_id
HWIS_ROLE_ID=optional_role_id
```

Notes:

- `config.py` loads `.env` automatically.
- The grading model is currently set in [config.py](/c:/Users/USER/OneDrive/Desktop/Stats/code/Bot/config.py:9) as `gpt-5-mini`.
- SQLite uses `homework.db` in the project root by default.
- The bot will automatically create local `uploads/` and `reports/` directories if they do not exist.

## Google Drive OAuth Setup

This project uploads both student submissions and generated reports to Google Drive. Before running the bot, place your Google OAuth client file in the project root as `credentials.json`, then run:

```bash
python script/oauth_setup.py
```

This will open the OAuth consent flow locally and generate `token.json`.

Required local files for Google Drive integration:

- `credentials.json`
- `token.json`

## Import Student Data

Student rosters are imported from Excel files in the `Course List/` directory. The importer attempts to detect these columns:

- student name
- student number
- password
- optional Discord ID

Run:

```bash
python script/student_importer.py
```

If your Excel workbook contains multiple sheets, the importer can infer class names from sheet names. Known class names currently used in the project include:

- `NCUFN`
- `NCUEC`
- `CYCUIUBM`

## How to Start the Bot

After dependencies, `.env`, `credentials.json`, `token.json`, and roster data are ready, start the bot with:

```bash
python main.py
```

To force the bot to resend welcome messages:

```bash
python main.py --force-welcome
```

The entry point is [main.py](/c:/Users/USER/OneDrive/Desktop/Stats/code/Bot/main.py:1), which creates `HomeworkBot` from [discord_bot.py](/c:/Users/USER/OneDrive/Desktop/Stats/code/Bot/discord_bot.py:26) and runs it.

## Discord Usage

### Student commands

- `!login 學號 密碼`
- `!my-submissions`
- Upload an `.html` file directly in the correct class channel

### Admin commands

- `!help`
- `!update-welcome`
- `!score 班級 題目`
- `!open`
- `!close`
- `!remove-role-members 身份組名稱`

## Grading Flow

1. The student logs in through Discord.
2. The bot identifies the student's class from the database.
3. The student uploads an HTML FRQ answer file.
4. The system extracts:
   - question title
   - student name
   - student ID
   - answer content
5. The bot selects the matching English and statistics prompts from `config.py`.
6. OpenAI generates two feedback sections.
7. The system builds an HTML report.
8. Submission metadata and parsed scores are saved into SQLite.
9. Files are stored locally and uploaded to Google Drive.

## Data and Storage

This project currently uses:

- `homework.db` for SQLite records
- `uploads/` for raw uploaded student files
- `reports/` for generated HTML reports
- Google Drive for organized cloud storage

The database includes records for:

- classes
- students
- submission attempts
- parsed grading scores

## Troubleshooting

### Bot does not start

- Check that `.env` exists and `DISCORD_TOKEN` is correct
- Confirm all dependencies are installed
- Make sure `credentials.json` and `token.json` are available if Google Drive upload is enabled

### Login fails

- Confirm the student roster has been imported
- Check that the student ID and password exist in `homework.db`

### Grading does not run

- Check that the HTML title matches one of the configured question titles in `SPECIFIC_PROMPTS`
- Confirm `OPENAI_API_KEY` is valid
- Check the bot console for OpenAI timeout or prompt-loading errors

### Google Drive upload fails

- Re-run `python script/oauth_setup.py`
- Confirm `UPLOADS_FOLDER_ID` and `REPORTS_FOLDER_ID` are valid
- Check whether `token.json` has expired or lacks refresh permissions

## Deployment Notes

This project is best deployed as a persistent background service on a VM or server. Because it depends on:

- a long-running Discord connection
- local file storage
- SQLite
- Google OAuth credentials

it is more suitable for a VM or Docker-based deployment than a stateless frontend hosting platform.

## License

This repository currently does not define a license.
