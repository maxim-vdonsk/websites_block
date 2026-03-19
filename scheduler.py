"""
Планировщик задач и бизнес-логика блокировки.
Планировщик запускается в отдельном фоновом потоке (daemon),
чтобы не замораживать графический интерфейс.

Зависит от: db.py, hosts.py
"""

import time
import threading
import schedule

from db import add_websites_to_db, get_all_websites
from hosts import block_sites_in_hosts, unblock_sites_in_hosts


# Флаг для остановки цикла планировщика при повторном запуске
_scheduler_running = False


def validate_time(t: str) -> bool:
    """Проверяет, что строка соответствует формату ЧЧ:ММ.

    Returns:
        True — формат верный, False — неверный
    """
    try:
        time.strptime(t, "%H:%M")
        return True
    except ValueError:
        return False


def create_list(sites_input: str) -> bool:
    """Парсит строку с сайтами, сохраняет в БД и применяет блокировку в hosts.

    Args:
        sites_input: строка с доменами, разделёнными переносом строки

    Returns:
        True — успех, False — пустой список или ошибка прав доступа
    """
    websites = [s.strip() for s in sites_input.split("\n") if s.strip()]
    if not websites:
        return False
    add_websites_to_db(websites)
    all_sites = get_all_websites()
    return block_sites_in_hosts(all_sites)


def start_blocking(sites_input: str) -> None:
    """Включает блокировку. Вызывается планировщиком по расписанию."""
    print("Блокировка включена по расписанию.")
    create_list(sites_input)


def stop_blocking() -> None:
    """Снимает блокировку. Вызывается планировщиком по расписанию."""
    print("Блокировка снята по расписанию.")
    unblock_sites_in_hosts()


def _run_scheduler(start_time: str, stop_time: str, sites_input: str) -> None:
    """Внутренняя функция: запускает цикл планировщика.

    Не вызывать напрямую — только через start_scheduler_thread().
    """
    global _scheduler_running
    _scheduler_running = True

    schedule.clear()  # убираем задачи от предыдущего запуска
    schedule.every().day.at(start_time).do(start_blocking, sites_input)
    schedule.every().day.at(stop_time).do(stop_blocking)

    print(f"Расписание: блокировка с {start_time} до {stop_time}.")

    while _scheduler_running:
        schedule.run_pending()
        time.sleep(1)


def start_scheduler_thread(start_time: str, stop_time: str, sites_input: str) -> None:
    """Запускает планировщик в фоновом потоке-демоне.

    Поток-демон автоматически завершается при закрытии главного окна.
    При повторном вызове останавливает предыдущий поток и запускает новый.
    """
    global _scheduler_running
    _scheduler_running = False  # останавливаем предыдущий цикл (если был)

    thread = threading.Thread(
        target=_run_scheduler,
        args=(start_time, stop_time, sites_input),
        daemon=True,
        name="SchedulerThread"
    )
    thread.start()
