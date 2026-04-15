# bustanlik-ss-testing-system 🚀

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.x-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/Framework-aiogram-orange.svg" alt="AIOGram Framework">
  <img src="https://img.shields.io/badge/Database-PostgreSQL-blue.svg" alt="PostgreSQL Database">
  <img src="https://img.shields.io/github/stars/ss-diyor/bustanlik-ss-testing-system?style=social" alt="GitHub stars">
  <img src="https://img.shields.io/github/forks/ss-diyor/bustanlik-ss-testing-system?style=social" alt="GitHub forks">
</p>

## Project Title & Description

This repository hosts the **Bo'stonliq tuman ixtisoslashtirilgan maktabining DTM natijalarini hisoblash, sertifikat yaratish va reyting tizimi bot loyihasi**.

In English: This is a Telegram bot project designed for the Bo'stonliq District Specialized School to manage DTM (State Testing Center) results. It automates the calculation of test scores, generates official certificates for students, and maintains a comprehensive rating system. The system aims to streamline the process of result management and provide students and administrators with easy access to performance data and official documents.

## Key Features & Benefits

*   **Automated DTM Result Calculation:** Efficiently processes and calculates scores from DTM test results.
*   **Dynamic Certificate Generation:** Automatically creates personalized PDF certificates for students based on their test performance using `FPDF`.
*   **Comprehensive Rating System:** Implements a student ranking and rating system to track academic progress and competitiveness.
*   **Telegram Bot Interface:** Provides an intuitive and accessible interface for both students and administrators via Telegram.
*   **Student Self-Service:** Students can check their results, download certificates, and view their ratings directly through the bot.
*   **Administrator Dashboard:** Dedicated admin panel (via bot commands) for adding students, inputting test results, viewing detailed statistics, managing subjects/directions, and adjusting system settings.
*   **Robust Database Integration:** Utilizes PostgreSQL for reliable storage and management of student data, test results, and system configurations.
*   **Scalable Architecture:** Built with `aiogram` for asynchronous operations, ensuring responsiveness and scalability for multiple users.

## Prerequisites & Dependencies

Before setting up the project, ensure you have the following installed:

*   **Python 3.8+**
*   **PostgreSQL** database server

The project relies on several Python libraries. These will be installed during the setup process.

### Technologies Used

*   **Language:** Python
*   **Framework:** `aiogram` (for Telegram Bot API interaction)
*   **Database:** PostgreSQL

### Core Python Libraries

The following key libraries are used:

*   `aiogram`: For building the Telegram bot.
*   `psycopg2`: PostgreSQL adapter for Python.
*   `fpdf`: For generating PDF certificates.
*   `pandas`: Used in admin functionalities, likely for data processing and export.
*   `asyncio`: Python's built-in library for asynchronous I/O.
*   `python-dotenv` (recommended for local development to manage environment variables)

## Installation & Setup Instructions

Follow these steps to get the `bustanlik-ss-testing-system` up and running on your local machine or a server.

### 1. Clone the Repository

```bash
git clone https://github.com/ss-diyor/bustanlik-ss-testing-system.git
cd bustanlik-ss-testing-system
```

### 2. Set Up a Virtual Environment (Recommended)

```bash
python3 -m venv venv
source venv/bin/activate # On Windows use `venv\Scripts\activate`
```

### 3. Install Dependencies

Create a `requirements.txt` file in the root directory with the following content:

```
aiogram>=3.0.0
psycopg2-binary
fpdf
pandas
python-dotenv # Recommended for local environment variables
```

Then install them:

```bash
pip install -r requirements.txt
```

### 4. Database Setup

1.  **Create a PostgreSQL database.** For example, `bustanlik_db`.
2.  **Obtain your database connection URL.** It typically looks like: `postgres://user:password@host:port/database_name` (e.g., `postgres://admin:password@localhost:5432/bustanlik_db`).
3.  The bot uses a connection pool, so ensure your database is accessible. The `database.py` script includes an `init_db` function (called in `bot.py`), which will handle schema initialization on first run if the tables don't exist.

### 5. Configuration

Create a `.env` file in the root directory of your project (for local development) or set environment variables directly on your hosting platform (e.g., Railway, Heroku).

```dotenv
BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
ADMIN_PASSWORD="YOUR_SECURE_ADMIN_PASSWORD"
ADMIN_IDS="123456789,987654321" # Comma-separated list of Telegram user IDs for admins
DATABASE_URL="postgres://user:password@host:port/database_name"

# Optional: Adjust coefficients if needed
MAJBURIY_KOEFF=1.1
ASOSIY_1_KOEFF=1.1
ASOSIY_2_KOEFF=1.1

# Optional: Maximum questions (used in admin logic)
MAX_SAVOL=30
```

*   **`BOT_TOKEN`**: Get this from BotFather on Telegram.
*   **`ADMIN_PASSWORD`**: A password to gain admin access within the bot. Choose a strong one.
*   **`ADMIN_IDS`**: Your Telegram User ID and any other administrators' IDs. You can get your ID from bots like `@userinfobot`.
*   **`DATABASE_URL`**: The connection string for your PostgreSQL database.
*   **Coefficients**: These values (e.g., `MAJBURIY_KOEFF`) are used in score calculation. Adjust as per your school's scoring system.
*   **`MAX_SAVOL`**: Defines the maximum number of questions for a test, used in certain admin calculations.

### 6. Run the Bot

Once everything is configured, you can start the bot:

```bash
python bot.py
```

For deployment on platforms like Railway, a `Procfile` is provided to specify the command:

```
worker: python bot.py
```

## Usage Examples

This bot provides distinct functionalities for general users (students) and administrators.

### For Students (General Users)

1.  **Start the bot:** Send `/start` to your bot on Telegram.
2.  **Registration/Login:** If it's your first time, you might be prompted to register or link your Telegram account to an existing student profile in the school's system.
3.  **View Results:** Access your DTM test results directly.
4.  **Download Certificate:** Generate and download your official performance certificate in PDF format.
5.  **View Rating:** Check your standing in the school's overall rating system.

### For Administrators

1.  **Access Admin Panel:** Send `/start` to the bot. If your Telegram ID is in `ADMIN_IDS`, you will be prompted for the `ADMIN_PASSWORD` to gain access to the admin menu.
2.  **Add Students:** Register new students into the system.
3.  **Input Results:** Enter DTM test scores for students.
4.  **View Statistics:** Access detailed performance analytics and reports on student performance.
5.  **Manage Subjects/Directions:** Add, edit, or remove academic subjects and study directions within the system.
6.  **Update Settings:** Modify various bot and system settings, including score coefficients.
7.  **Generate Bulk Certificates:** (Likely) Generate certificates for multiple students or specific groups.

The bot's menu structure (defined in `keyboards.py`) guides users through available actions.

## Configuration Options

All critical configuration settings are managed through environment variables, which can be set in a `.env` file for local development or directly on your hosting provider.

| Variable Name      | Description                                                     | Default (if not set)    | Source File      |
| :----------------- | :-------------------------------------------------------------- | :---------------------- | :--------------- |
| `BOT_TOKEN`        | Your Telegram Bot API token.                                    | `"YOUR_BOT_TOKEN_HERE"` | `config.py`      |
| `ADMIN_PASSWORD`   | Password to unlock administrative features in the bot.          | `"admin123"`            | `config.py`      |
| `ADMIN_IDS`        | Comma-separated Telegram User IDs of authorized administrators. | `[1234567890]`          | `config.py`      |
| `DATABASE_URL`     | PostgreSQL database connection string.                          | `None`                  | `database.py`    |
| `MAJBURIY_KOEFF`   | Coefficient for mandatory subjects' scores.                     | `1.1`                   | `config.py`      |
| `ASOSIY_1_KOEFF`   | Coefficient for primary core subject 1 scores.                  | `1.1`                   | `config.py`      |
| `ASOSIY_2_KOEFF`   | Coefficient for primary core subject 2 scores.                  | `1.1`                   | `config.py`      |
| `MAX_SAVOL`        | Maximum number of questions considered in certain calculations. | `30`                    | `config.py`      |

It is **highly recommended** to set these variables securely, especially `BOT_TOKEN`, `ADMIN_PASSWORD`, and `DATABASE_URL`.

## Contributing Guidelines

We welcome contributions to improve the `bustanlik-ss-testing-system`! To contribute, please follow these steps:

1.  **Fork** the repository on GitHub.
2.  **Clone** your forked repository to your local machine.
3.  **Create a new branch** for your feature or bug fix: `git checkout -b feature/your-feature-name` or `fix/bug-description`.
4.  **Make your changes**, adhering to the existing code style.
5.  **Test your changes** thoroughly.
6.  **Commit your changes** with a clear and concise commit message.
7.  **Push your branch** to your forked repository.
8.  **Open a Pull Request** against the `main` branch of the original repository, describing your changes in detail.

## License Information

This project currently does not have a specified license. By default, this means all rights are reserved by the copyright holder (`ss-diyor`).

It is recommended to add an open-source license (e.g., MIT, Apache 2.0, GPL) to clarify usage, modification, and distribution terms.

## Acknowledgments

We extend our gratitude to the developers of the following open-source projects, whose libraries made this bot possible:

*   **`aiogram`**: A modern and fully asynchronous framework for Telegram Bot API.
*   **`psycopg2`**: The most popular PostgreSQL adapter for the Python programming language.
*   **`fpdf`**: A Python class which allows to generate PDF files with Python.
*   **`pandas`**: A powerful data manipulation and analysis library.

This project is maintained by **ss-diyor**.
