from krita import Extension, Krita
from PyQt5.QtWidgets import QMessageBox
from .pie_widget import PieMenuWidget

class PieMenuExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)
        self.pie_widget = None

    def setup(self):
        pass

    def createActions(self, window):
        action = window.createAction("trigger_pie_menu", "Philosophical Pie Menu", "tools/scripts")
        action.triggered.connect(self.show_pie_menu)

    def show_pie_menu(self):
        callbacks = {
            'north': self.func_rousseau,
            'east':  self.func_descartes,
            'south': self.func_socrates,
            'west':  self.func_nietzsche,
        }
        self.pie_widget = PieMenuWidget(callbacks)
        self.pie_widget.show_at_cursor()

    # 4 Dummy Functions displaying Philosophical Phrases
    def func_rousseau(self):
        QMessageBox.information(
            None,
            "Jean-Jacques Rousseau",
            "\"Man is born free, and everywhere he is in chains.\"\n\n— Jean-Jacques Rousseau (The Social Contract, 1762)"
        )

    def func_descartes(self):
        QMessageBox.information(
            None,
            "René Descartes",
            "\"I think, therefore I am.\" (Cogito, ergo sum)\n\n— René Descartes (Discourse on the Method, 1637)"
        )

    def func_socrates(self):
        QMessageBox.information(
            None,
            "Socrates",
            "\"The unexamined life is not worth living.\"\n\n— Socrates (Apology by Plato)"
        )

    def func_nietzsche(self):
        QMessageBox.information(
            None,
            "Friedrich Nietzsche",
            "\"He who has a why to live can bear almost any how.\"\n\n— Friedrich Nietzsche (Twilight of the Idols, 1889)"
        )
