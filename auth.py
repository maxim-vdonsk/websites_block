"""
Аутентификация: хэширование паролей и проверка при входе.
Зависит от: db.py
"""

import hashlib

from db import create_tables, get_password_from_db


def hash_password(password: str) -> str:
    """Возвращает SHA-256 хэш строки пароля."""
    return hashlib.sha256(password.encode()).hexdigest()


def password_check() -> tuple[str | None, bool]:
    """Проверяет, установлен ли пароль в базе данных.

    Возвращает:
        (hashed_password, True)  — пароль уже задан
        (None, False)            — первый запуск, пароль не задан
    """
    create_tables()  # гарантируем, что таблицы существуют перед запросом
    stored = get_password_from_db()
    return (stored, True) if stored else (None, False)
