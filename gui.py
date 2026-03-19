"""
Графический интерфейс приложения (Tkinter).
Сначала показывает окно ввода пароля, после успешного входа — основное окно.

Зависит от: auth.py, db.py, hosts.py, scheduler.py, config.py
"""

import tkinter as tk
from tkinter import messagebox

from config import HOSTS_FILE
from auth import hash_password, password_check
from db import save_password_to_db, get_all_websites, clear_websites_db
from hosts import unblock_sites_in_hosts
from scheduler import create_list, start_scheduler_thread, validate_time


class App:
    """Главный класс приложения с GUI на Tkinter."""

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
        """Проверяет введённый пароль. При первом запуске сохраняет новый."""
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
        """Валидирует ввод и запускает планировщик в фоновом потоке."""
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
