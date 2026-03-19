"""
Точка входа приложения «Блокировщик сайтов».
Запускать: python main.py  (на macOS/Linux — sudo python main.py)
"""

import tkinter as tk

from gui import App

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
