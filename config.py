"""
Константы и настройки приложения.
Этот файл не импортирует ничего из других модулей проекта.
"""

import os
import platform

# IP-адрес, на который перенаправляются заблокированные сайты
REDIRECT_IP = "127.0.0.1"

# Путь к базе данных — рядом со скриптом, не зависит от рабочей директории
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_data.db")

# Путь к hosts-файлу определяется автоматически по операционной системе
if platform.system() == "Windows":
    HOSTS_FILE = r"C:\Windows\System32\drivers\etc\hosts"
else:
    HOSTS_FILE = "/etc/hosts"  # Linux / macOS

# Маркеры — по ним программа находит свои строки в hosts и удаляет только их
HOSTS_MARKER_START = "# --- WEBSITE BLOCKER START ---"
HOSTS_MARKER_END   = "# --- WEBSITE BLOCKER END ---"
