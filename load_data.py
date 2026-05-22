import tkinter as tk

from app.ui.main_window import SNIESConsolidador


def main() -> None:
    root = tk.Tk()
    SNIESConsolidador(root)
    root.mainloop()


if __name__ == "__main__":
    main()
