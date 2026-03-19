"""
Блокировщик сайтов с расписанием
Автор: maxim_vdonsk
"""

import sqlite3
import os
import hashlib
import platform
import schedule
import time
import threading
import tkinter as tk
from tkinter import messagebox


# ============================================================
# КОНСТАНТЫ
# ============================================================

REDIRECT_IP = "127.0.0.1"

# Путь к базе данных рядом с самим скриптом
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_data.db")

# Путь к hosts-файлу определяется автоматически по ОС
if platform.system() == "Windows":
    HOSTS_FILE = r"C:\Windows\System32\drivers\etc\hosts"
else:
    HOSTS_FILE = "/etc/hosts"  # Linux / macOS

# Маркеры — по ним программа находит свои строки в hosts и удаляет их
HOSTS_MARKER_START = "# --- WEBSITE BLOCKER START ---"
HOSTS_MARKER_END   = "# --- WEBSITE BLOCKER END ---"


# ============================================================
# ХЭШИРОВАНИЕ ПАРОЛЕЙ
# ============================================================

def hash_password(password: str) -> str:
    """Возвращает SHA-256 хэш строки пароля."""
    return hashlib.sha256(password.encode()).hexdigest()


# ============================================================
# БАЗА ДАННЫХ (SQLite)
# ============================================================

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
    """Возвращает сохранённый хэш пароля или None, если пароль ещё не задан."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM passwords WHERE id = 1")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def save_password_to_db(hashed_password: str) -> None:
    """Сохраняет хэш пароля.

    INSERT OR REPLACE безопасно работает как при первом сохранении,
    так и при последующих обновлениях пароля.
    """
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


# ============================================================
# РАБОТА С HOSTS-ФАЙЛОМ
# ============================================================

def _read_hosts() -> str:
    """Читает и возвращает содержимое hosts-файла."""
    try:
        with open(HOSTS_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except PermissionError:
        return ""
    except FileNotFoundError:
        return ""


def _write_hosts(content: str) -> bool:
    """Записывает content в hosts-файл. Возвращает True при успехе."""
    try:
        with open(HOSTS_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except PermissionError:
        return False


def _remove_blocker_block(content: str) -> str:
    """Удаляет блок строк между маркерами (включая сами маркеры) из текста hosts."""
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

    Если блок уже существует — заменяет его.
    Также добавляет www-вариант домена, если он не указан явно.
    Возвращает True при успехе, False при ошибке прав доступа.
    """
    content = _read_hosts()

    # Убираем старый блок (если был)
    content = _remove_blocker_block(content)

    # Формируем новый блок
    block_lines = [HOSTS_MARKER_START]
    for site in sites:
        block_lines.append(f"{REDIRECT_IP} {site}")
        # Блокируем и www-вариант, если его нет в списке
        if not site.startswith("www."):
            block_lines.append(f"{REDIRECT_IP} www.{site}")
    block_lines.append(HOSTS_MARKER_END)

    new_content = content.rstrip("\n") + "\n" + "\n".join(block_lines) + "\n"
    return _write_hosts(new_content)


def unblock_sites_in_hosts() -> bool:
    """Удаляет блок записей блокировщика из hosts-файла.

    Возвращает True при успехе, False при ошибке прав доступа.
    """
    content = _read_hosts()
    new_content = _remove_blocker_block(content)
    return _write_hosts(new_content)


# ============================================================
# БИЗНЕС-ЛОГИКА
# ============================================================

def password_check() -> tuple[str | None, bool]:
    """Проверяет, установлен ли пароль в БД.

    Возвращает:
        (hashed_password, True)  — пароль уже задан
        (None, False)            — первый запуск, пароль ещё не задан
    """
    create_tables()
    stored = get_password_from_db()
    return (stored, True) if stored else (None, False)


def validate_time(t: str) -> bool:
    """Возвращает True, если строка соответствует формату ЧЧ:ММ."""
    try:
        time.strptime(t, "%H:%M")
        return True
    except ValueError:
        return False


def create_list(sites_input: str) -> bool:
    """Парсит строку сайтов, сохраняет в БД и блокирует в hosts.

    Args:
        sites_input: строка с сайтами, разделёнными переносом строки.

    Returns:
        True при успехе, False при ошибке (например, нет прав или пустой список).
    """
    websites = [s.strip() for s in sites_input.split("\n") if s.strip()]
    if not websites:
        return False
    add_websites_to_db(websites)
    all_sites = get_all_websites()
    return block_sites_in_hosts(all_sites)


# ============================================================
# ПЛАНИРОВЩИК
# ============================================================

# Флаг для остановки фонового потока планировщика
_scheduler_running = False


def start_blocking(sites_input: str) -> None:
    """Включает блокировку сайтов. Вызывается планировщиком по расписанию."""
    print("Блокировка включена по расписанию.")
    create_list(sites_input)


def stop_blocking() -> None:
    """Снимает блокировку сайтов. Вызывается планировщиком по расписанию."""
    print("Блокировка снята по расписанию.")
    unblock_sites_in_hosts()


def schedule_tasks(start_time: str, stop_time: str, sites_input: str) -> None:
    """Запускает планировщик в бесконечном цикле.

    Предназначен для вызова только из отдельного потока.
    Цикл завершается, когда _scheduler_running становится False.
    """
    global _scheduler_running
    _scheduler_running = True

    # Очищаем задачи от предыдущего запуска, чтобы не было дублей
    schedule.clear()

    schedule.every().day.at(start_time).do(start_blocking, sites_input)
    schedule.every().day.at(stop_time).do(stop_blocking)

    print(f"Расписание установлено: блокировка с {start_time} до {stop_time}.")

    while _scheduler_running:
        schedule.run_pending()
        time.sleep(1)


def start_scheduler_thread(start_time: str, stop_time: str, sites_input: str) -> None:
    """Запускает планировщик в фоновом потоке-демоне.

    Поток-демон автоматически завершается при закрытии главного окна.
    """
    global _scheduler_running
    _scheduler_running = False  # Останавливаем предыдущий поток (если был)

    thread = threading.Thread(
        target=schedule_tasks,
        args=(start_time, stop_time, sites_input),
        daemon=True,
        name="SchedulerThread"
    )
    thread.start()


# ============================================================
# ГРАФИЧЕСКИЙ ИНТЕРФЕЙС (TKINTER)
# ============================================================

class App:
    """Главный класс приложения с GUI на Tkinter.

    Сначала показывает окно ввода пароля.
    После успешного входа — основное окно управления блокировкой.
    """

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Блокировщик сайтов")
        self.root.resizable(False, False)
        self._build_password_window()

    # ----------------------------------------------------------
    # Окно ввода / создания пароля
    # ----------------------------------------------------------

    def _build_password_window(self) -> None:
        """Строит фрейм с полем ввода пароля и кнопкой входа."""
        self.password_frame = tk.Frame(self.root)
        self.password_frame.pack(padx=30, pady=30)

        tk.Label(self.password_frame, text="Введите пароль:").grid(
            row=0, column=0, sticky="e", padx=5
        )

        self.password_entry = tk.Entry(self.password_frame, show="*", width=25)
        self.password_entry.grid(row=0, column=1, padx=5)
        self.password_entry.focus_set()
        # Enter работает как кнопка «Войти»
        self.password_entry.bind("<Return>", lambda _: self._check_password())

        tk.Button(
            self.password_frame, text="Войти", command=self._check_password
        ).grid(row=0, column=2, padx=5)

    def _check_password(self) -> None:
        """Проверяет пароль. При первом запуске — сохраняет новый."""
        stored_password, is_existing = password_check()
        entered = self.password_entry.get()

        if not entered.strip():
            messagebox.showerror("Ошибка", "Пароль не может быть пустым.")
            return

        if is_existing:
            # Пароль уже задан — сверяем хэши
            if hash_password(entered) == stored_password:
                self.password_frame.destroy()
                self._build_main_window()
            else:
                messagebox.showerror("Ошибка", "Неверный пароль.")
                self.password_entry.delete(0, tk.END)
        else:
            # Первый запуск — создаём пароль
            save_password_to_db(hash_password(entered))
            messagebox.showinfo("Успех", "Пароль сохранён!\nПерезапустите приложение.")
            self.root.quit()

    # ----------------------------------------------------------
    # Главное окно управления блокировкой
    # ----------------------------------------------------------

    def _build_main_window(self) -> None:
        """Строит основной интерфейс после успешного входа."""

        # --- Список сайтов ---
        sites_frame = tk.LabelFrame(self.root, text="Сайты для блокировки", padx=10, pady=10)
        sites_frame.pack(padx=20, pady=(20, 5), fill="x")

        tk.Label(sites_frame, text="Один сайт на строку (например: youtube.com):").pack(anchor="w")

        self.sites_text = tk.Text(sites_frame, height=7, width=45)
        self.sites_text.pack()

        # Загружаем ранее сохранённые сайты из базы данных
        for site in get_all_websites():
            self.sites_text.insert(tk.END, site + "\n")

        # --- Настройка расписания ---
        time_frame = tk.LabelFrame(self.root, text="Расписание блокировки", padx=10, pady=10)
        time_frame.pack(padx=20, pady=5, fill="x")

        tk.Label(time_frame, text="Время начала   (ЧЧ:ММ):").grid(
            row=0, column=0, sticky="e", pady=2
        )
        self.start_time_entry = tk.Entry(time_frame, width=10)
        self.start_time_entry.grid(row=0, column=1, padx=5, sticky="w")

        tk.Label(time_frame, text="Время окончания (ЧЧ:ММ):").grid(
            row=1, column=0, sticky="e", pady=2
        )
        self.stop_time_entry = tk.Entry(time_frame, width=10)
        self.stop_time_entry.grid(row=1, column=1, padx=5, sticky="w")

        # --- Кнопки действий ---
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(padx=20, pady=15)

        tk.Button(
            btn_frame, text="Запуск по расписанию",
            width=20, command=self._set_schedule
        ).grid(row=0, column=0, padx=5)

        tk.Button(
            btn_frame, text="Заблокировать сейчас",
            width=20, command=self._block_immediately
        ).grid(row=0, column=1, padx=5)

        tk.Button(
            btn_frame, text="Разблокировать всё",
            width=20, command=self._clear_websites
        ).grid(row=0, column=2, padx=5)

        # Статусная строка внизу окна
        self.status_var = tk.StringVar(value="Готово.")
        tk.Label(self.root, textvariable=self.status_var, fg="gray").pack(pady=(0, 10))

    # ----------------------------------------------------------
    # Обработчики кнопок
    # ----------------------------------------------------------

    def _get_sites_input(self) -> str:
        """Возвращает текст из поля ввода сайтов."""
        return self.sites_text.get("1.0", "end-1c")

    def _set_schedule(self) -> None:
        """Устанавливает расписание блокировки и запускает фоновый поток."""
        start_time = self.start_time_entry.get().strip()
        stop_time  = self.stop_time_entry.get().strip()

        if not start_time or not stop_time:
            messagebox.showerror("Ошибка", "Укажите время начала и окончания.")
            return

        if not validate_time(start_time) or not validate_time(stop_time):
            messagebox.showerror(
                "Ошибка формата",
                "Неверный формат времени.\nИспользуйте ЧЧ:ММ, например: 09:00"
            )
            return

        sites_input = self._get_sites_input()
        if not sites_input.strip():
            messagebox.showerror("Ошибка", "Список сайтов пуст.")
            return

        start_scheduler_thread(start_time, stop_time, sites_input)
        self.status_var.set(f"Расписание: блокировка с {start_time} до {stop_time}.")
        messagebox.showinfo(
            "Расписание установлено",
            f"Блокировка включится в {start_time}\nи снимется в {stop_time}."
        )

    def _block_immediately(self) -> None:
        """Немедленно блокирует сайты из поля ввода."""
        sites_input = self._get_sites_input()
        if not sites_input.strip():
            messagebox.showerror("Ошибка", "Список сайтов пуст.")
            return

        success = create_list(sites_input)
        if success:
            self.status_var.set("Сайты заблокированы.")
            messagebox.showinfo("Успех", "Сайты заблокированы.")
        else:
            messagebox.showerror(
                "Ошибка прав доступа",
                f"Не удалось изменить файл:\n{HOSTS_FILE}\n\n"
                "Запустите программу от имени администратора:\n"
                "  macOS/Linux:  sudo python main.py\n"
                "  Windows: запустить от администратора"
            )

    def _clear_websites(self) -> None:
        """Очищает список сайтов в БД и снимает блокировку в hosts."""
        clear_websites_db()
        success = unblock_sites_in_hosts()

        self.sites_text.delete("1.0", tk.END)

        if success:
            self.status_var.set("Все сайты разблокированы.")
            messagebox.showinfo("Успех", "Сайты разблокированы.")
        else:
            messagebox.showerror(
                "Ошибка прав доступа",
                f"Не удалось изменить файл:\n{HOSTS_FILE}\n\n"
                "Запустите программу от имени администратора."
            )


# ============================================================
# ТОЧКА ВХОДА
# ============================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
