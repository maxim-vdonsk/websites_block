"""
Работа с базой данных SQLite.
Таблицы:
  passwords — хранит один хэш пароля (id=1)
  websites  — список сайтов для блокировки
"""

import sqlite3

from config import DB_PATH


def create_tables() -> None:
    """Создаёт таблицы passwords и websites, если они ещё не существуют."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS passwords (
            id       INTEGER PRIMARY KEY,
            password TEXT    NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS websites (
            id  INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT    NOT NULL UNIQUE
        )
    """)

    conn.commit()
    conn.close()


def get_password_from_db() -> str | None:
    """Возвращает сохранённый хэш пароля или None, если пароль не задан."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM passwords WHERE id = 1")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def save_password_to_db(hashed_password: str) -> None:
    """Сохраняет хэш пароля (INSERT OR REPLACE — работает и при первом, и при повторном вызове)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO passwords (id, password) VALUES (1, ?)",
        (hashed_password,)
    )
    conn.commit()
    conn.close()


def add_websites_to_db(websites: list[str]) -> None:
    """Добавляет сайты в базу данных, пропуская уже существующие (INSERT OR IGNORE)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for site in websites:
        cursor.execute("INSERT OR IGNORE INTO websites (url) VALUES (?)", (site,))
    conn.commit()
    conn.close()


def get_all_websites() -> list[str]:
    """Возвращает список всех сайтов из базы данных."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT url FROM websites")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


def clear_websites_db() -> None:
    """Удаляет все записи о сайтах из базы данных."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM websites")
    conn.commit()
    conn.close()
