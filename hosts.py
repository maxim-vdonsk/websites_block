"""
Работа с системным hosts-файлом.
Программа добавляет и удаляет только свой блок, ограниченный маркерами,
не затрагивая остальное содержимое файла.

Зависит от: config.py
"""

from config import REDIRECT_IP, HOSTS_FILE, HOSTS_MARKER_START, HOSTS_MARKER_END


def _read_hosts() -> str:
    """Читает содержимое hosts-файла. При ошибке прав доступа возвращает пустую строку."""
    try:
        with open(HOSTS_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except (PermissionError, FileNotFoundError):
        return ""


def _write_hosts(content: str) -> bool:
    """Записывает content в hosts-файл.

    Returns:
        True — запись прошла успешно
        False — нет прав доступа (нужен sudo / администратор)
    """
    try:
        with open(HOSTS_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except PermissionError:
        return False


def _remove_blocker_block(content: str) -> str:
    """Удаляет строки между маркерами (включая сами маркеры) из текста hosts.

    Все остальные строки файла остаются нетронутыми.
    """
    lines = content.splitlines(keepends=True)
    result = []
    inside_block = False

    for line in lines:
        if HOSTS_MARKER_START in line:
            inside_block = True
            continue
        if HOSTS_MARKER_END in line:
            inside_block = False
            continue
        if not inside_block:
            result.append(line)

    return "".join(result)


def block_sites_in_hosts(sites: list[str]) -> bool:
    """Добавляет записи блокировки в hosts-файл между маркерами.

    Если блок уже существует — заменяет его целиком.
    Автоматически добавляет www-вариант домена, если его нет в списке.

    Args:
        sites: список доменов для блокировки (например, ['youtube.com', 'vk.com'])

    Returns:
        True — успех, False — ошибка прав доступа
    """
    content = _read_hosts()
    content = _remove_blocker_block(content)  # убираем старый блок

    # Формируем новый блок с маркерами
    block_lines = [HOSTS_MARKER_START]
    for site in sites:
        block_lines.append(f"{REDIRECT_IP} {site}")
        # Блокируем и www-вариант, если его явно не указали
        if not site.startswith("www."):
            block_lines.append(f"{REDIRECT_IP} www.{site}")
    block_lines.append(HOSTS_MARKER_END)

    new_content = content.rstrip("\n") + "\n" + "\n".join(block_lines) + "\n"
    return _write_hosts(new_content)


def unblock_sites_in_hosts() -> bool:
    """Удаляет блок записей блокировщика из hosts-файла.

    Returns:
        True — успех, False — ошибка прав доступа
    """
    content = _read_hosts()
    new_content = _remove_blocker_block(content)
    return _write_hosts(new_content)
