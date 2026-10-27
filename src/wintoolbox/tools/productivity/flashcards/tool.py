"""
Interface de usuário para o Sistema de Flashcards com algoritmo SuperMemo (SM-2).
"""
from datetime import date
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.settings import get_settings_dir
from wintoolbox.tools.productivity.flashcards.logic import (
    Deck,
    Flashcard,
    calculate_sm2,
    export_flashcards_to_csv,
    import_flashcards_from_csv,
    is_card_due,
    load_flashcards_data,
    save_flashcards_data,
)


@register
class FlashcardsTool(Tool):
    """Sistema de memorização e estudo baseado no algoritmo SuperMemo SM-2."""

    id = "productivity.flashcards"
    name = "Cartões de Memorização (Flashcards SM-2)"
    description = "Aumente sua retenção de conteúdo com repetição espaçada inteligente, gestão de baralhos e importação CSV."
    category = "productivity"

    def __init__(self):
        super().__init__()
        self.storage_path = get_settings_dir() / "flashcards.json"
        self.decks, self.cards = load_flashcards_data(self.storage_path)
        self.current_study_cards: List[Flashcard] = []
        self.study_index = 0
        self.is_answer_revealed = False

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Cabeçalho
        title = QLabel("Cartões de Estudo & Repetição Espaçada (SM-2)")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Algoritmo SuperMemo que calcula o momento exato em que seu cérebro está prestes a esquecer a informação."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        # Aba 1: Sessão de Estudo
        self.tab_study = self._build_study_tab()
        self.tabs.addTab(self.tab_study, "Sessão de Revisão")

        # Aba 2: Gerenciar Baralhos & Cartões
        self.tab_manage = self._build_manage_tab()
        self.tabs.addTab(self.tab_manage, "Gerenciar Baralhos e Cartões")

        self.tabs.currentChanged.connect(self._on_tab_changed)

        return widget

    def _save_data(self) -> None:
        save_flashcards_data(self.decks, self.cards, self.storage_path)

    def _on_tab_changed(self, idx: int) -> None:
        if idx == 0:
            self._start_study_session()
        else:
            self._refresh_manage_decks()

    # -------------------------------------------------------------
    # ABA DE ESTUDOS (SM-2)
    # -------------------------------------------------------------
    def _build_study_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # Barra de seleção de deck e status
        deck_bar = QHBoxLayout()
        deck_bar.addWidget(QLabel("Baralho de Estudo:"))
        self.cmb_study_deck = QComboBox()
        self.cmb_study_deck.currentIndexChanged.connect(self._on_study_deck_changed)
        deck_bar.addWidget(self.cmb_study_deck, 1)

        self.lbl_study_count = QLabel("0 cartões pendentes hoje")
        self.lbl_study_count.setStyleSheet("font-weight: bold; color: #0284c7;")
        deck_bar.addWidget(self.lbl_study_count)

        btn_restart = QPushButton("Recomeçar Sessão")
        btn_restart.clicked.connect(self._start_study_session)
        deck_bar.addWidget(btn_restart)
        layout.addLayout(deck_bar)

        # Barra de progresso
        self.prog_study = QProgressBar()
        self.prog_study.setFixedHeight(6)
        self.prog_study.setTextVisible(False)
        layout.addWidget(self.prog_study)

        # Card Visual Central
        self.card_frame = QFrame()
        self.card_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border: 2px solid rgba(128, 128, 128, 0.2); "
            "border-radius: 12px; padding: 20px; }"
        )
        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setSpacing(15)

        self.lbl_card_prompt = QLabel("PERGUNTA / FRENTE")
        self.lbl_card_prompt.setStyleSheet("font-size: 11px; font-weight: bold; color: #888888;")
        card_layout.addWidget(self.lbl_card_prompt)

        self.lbl_card_front = QLabel("Selecione um baralho para começar...")
        self.lbl_card_front.setWordWrap(True)
        self.lbl_card_front.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_card_front.setStyleSheet("font-size: 18px; font-weight: bold; min-height: 80px;")
        card_layout.addWidget(self.lbl_card_front, 1)

        self.div_card = QFrame()
        self.div_card.setFrameShape(QFrame.Shape.HLine)
        self.div_card.setStyleSheet("color: rgba(128, 128, 128, 0.3);")
        self.div_card.setVisible(False)
        card_layout.addWidget(self.div_card)

        self.lbl_card_answer_prompt = QLabel("RESPOSTA / VERSO")
        self.lbl_card_answer_prompt.setStyleSheet("font-size: 11px; font-weight: bold; color: #16a34a;")
        self.lbl_card_answer_prompt.setVisible(False)
        card_layout.addWidget(self.lbl_card_answer_prompt)

        self.lbl_card_back = QLabel("")
        self.lbl_card_back.setWordWrap(True)
        self.lbl_card_back.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_card_back.setStyleSheet("font-size: 16px; color: #3b82f6; min-height: 80px;")
        self.lbl_card_back.setVisible(False)
        card_layout.addWidget(self.lbl_card_back, 1)

        layout.addWidget(self.card_frame, 1)

        # Botão Revelar
        self.btn_reveal = QPushButton("Mostrar Resposta")
        self.btn_reveal.setFixedHeight(40)
        self.btn_reveal.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #0284c7; color: white; border-radius: 6px;")
        self.btn_reveal.clicked.connect(self._reveal_answer)
        layout.addWidget(self.btn_reveal)

        # Botões de Avaliação SM-2 (Qualidade de 0 a 5)
        self.box_rating = QHBoxLayout()
        self.box_rating.setSpacing(10)

        # 0: Errei
        self.btn_rate_0 = QPushButton("Errei (0)")
        self.btn_rate_0.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        self.btn_rate_0.clicked.connect(lambda: self._rate_card(0))
        self.box_rating.addWidget(self.btn_rate_0)

        # 3: Difícil
        self.btn_rate_3 = QPushButton("Difícil (3)")
        self.btn_rate_3.setStyleSheet("background-color: #ea580c; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        self.btn_rate_3.clicked.connect(lambda: self._rate_card(3))
        self.box_rating.addWidget(self.btn_rate_3)

        # 4: Bom
        self.btn_rate_4 = QPushButton("Bom (4)")
        self.btn_rate_4.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        self.btn_rate_4.clicked.connect(lambda: self._rate_card(4))
        self.box_rating.addWidget(self.btn_rate_4)

        # 5: Fácil
        self.btn_rate_5 = QPushButton("Fácil (5)")
        self.btn_rate_5.setStyleSheet("background-color: #16a34a; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        self.btn_rate_5.clicked.connect(lambda: self._rate_card(5))
        self.box_rating.addWidget(self.btn_rate_5)

        layout.addLayout(self.box_rating)
        self._set_rating_visible(False)

        self._refresh_study_deck_combo()
        return page

    def _refresh_study_deck_combo(self) -> None:
        self.cmb_study_deck.blockSignals(True)
        self.cmb_study_deck.clear()
        self.cmb_study_deck.addItem("Todos os Baralhos", "")
        for d in self.decks:
            self.cmb_study_deck.addItem(d.name, d.id)
        self.cmb_study_deck.blockSignals(False)

    def _on_study_deck_changed(self) -> None:
        self._start_study_session()

    def _start_study_session(self) -> None:
        self._refresh_study_deck_combo()
        sel_deck_id = self.cmb_study_deck.currentData()

        # Filtra os cartões devidos hoje
        today = date.today()
        self.current_study_cards = [
            c for c in self.cards
            if (not sel_deck_id or c.deck_id == sel_deck_id) and is_card_due(c, today)
        ]

        self.study_index = 0
        self.lbl_study_count.setText(f"{len(self.current_study_cards)} pendente(s) hoje")
        self.prog_study.setMaximum(max(1, len(self.current_study_cards)))
        self.prog_study.setValue(0)
        self._show_current_card()

    def _show_current_card(self) -> None:
        if not self.current_study_cards or self.study_index >= len(self.current_study_cards):
            self.lbl_card_front.setText("🎉 Parabéns!\nVocê concluiu todas as revisões pendentes para este baralho!")
            self.lbl_card_back.setText("")
            self.btn_reveal.setVisible(False)
            self._set_rating_visible(False)
            self.div_card.setVisible(False)
            self.lbl_card_answer_prompt.setVisible(False)
            self.prog_study.setValue(self.prog_study.maximum())
            return

        card = self.current_study_cards[self.study_index]
        self.lbl_card_front.setText(card.front)
        self.lbl_card_back.setText(card.back)

        self.btn_reveal.setVisible(True)
        self._set_rating_visible(False)
        self.div_card.setVisible(False)
        self.lbl_card_answer_prompt.setVisible(False)
        self.lbl_card_back.setVisible(False)

        self.prog_study.setValue(self.study_index)

    def _reveal_answer(self) -> None:
        self.btn_reveal.setVisible(False)
        self.div_card.setVisible(True)
        self.lbl_card_answer_prompt.setVisible(True)
        self.lbl_card_back.setVisible(True)
        self._set_rating_visible(True)

    def _set_rating_visible(self, visible: bool) -> None:
        self.btn_rate_0.setVisible(visible)
        self.btn_rate_3.setVisible(visible)
        self.btn_rate_4.setVisible(visible)
        self.btn_rate_5.setVisible(visible)

    def _rate_card(self, quality: int) -> None:
        if not self.current_study_cards or self.study_index >= len(self.current_study_cards):
            return

        card = self.current_study_cards[self.study_index]
        updated = calculate_sm2(card, quality, date.today())

        # Atualiza o card na lista global
        for idx, c in enumerate(self.cards):
            if c.id == card.id:
                self.cards[idx] = updated
                break

        self._save_data()
        self.study_index += 1
        self._show_current_card()

    # -------------------------------------------------------------
    # ABA DE GERENCIAMENTO (DECKS E CARDS)
    # -------------------------------------------------------------
    def _build_manage_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Barra de baralhos
        bar_deck = QHBoxLayout()
        bar_deck.addWidget(QLabel("Baralho Selecionado:"))
        self.cmb_manage_deck = QComboBox()
        self.cmb_manage_deck.currentIndexChanged.connect(self._refresh_manage_cards)
        bar_deck.addWidget(self.cmb_manage_deck, 1)

        btn_new_deck = QPushButton("+ Novo Baralho")
        btn_new_deck.clicked.connect(self._on_new_deck)
        bar_deck.addWidget(btn_new_deck)

        btn_del_deck = QPushButton("Excluir Baralho")
        btn_del_deck.setStyleSheet("color: #dc2626;")
        btn_del_deck.clicked.connect(self._on_delete_deck)
        bar_deck.addWidget(btn_del_deck)

        layout.addLayout(bar_deck)

        # Tabela de cartões do baralho
        self.tbl_cards = QTableWidget(0, 4)
        self.tbl_cards.setHorizontalHeaderLabels(["Frente (Pergunta)", "Verso (Resposta)", "Próx. Revisão", "Intervalo"])
        self.tbl_cards.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_cards.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_cards.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_cards.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_cards.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.tbl_cards, 1)

        # Botões de ações dos cartões
        action_bar = QHBoxLayout()
        btn_add_card = QPushButton("+ Novo Cartão")
        btn_add_card.setStyleSheet("font-weight: bold; background-color: #0284c7; color: white;")
        btn_add_card.clicked.connect(self._on_add_card)
        action_bar.addWidget(btn_add_card)

        btn_rem_card = QPushButton("Remover Selecionado")
        btn_rem_card.clicked.connect(self._on_remove_card)
        action_bar.addWidget(btn_rem_card)

        action_bar.addStretch()

        btn_import_csv = QPushButton("Importar CSV...")
        btn_import_csv.clicked.connect(self._on_import_csv)
        action_bar.addWidget(btn_import_csv)

        btn_export_csv = QPushButton("Exportar CSV...")
        btn_export_csv.clicked.connect(self._on_export_csv)
        action_bar.addWidget(btn_export_csv)

        layout.addLayout(action_bar)

        return page

    def _refresh_manage_decks(self) -> None:
        self.cmb_manage_deck.blockSignals(True)
        self.cmb_manage_deck.clear()
        for d in self.decks:
            self.cmb_manage_deck.addItem(d.name, d.id)
        self.cmb_manage_deck.blockSignals(False)
        self._refresh_manage_cards()

    def _refresh_manage_cards(self) -> None:
        deck_id = self.cmb_manage_deck.currentData()
        cards = [c for c in self.cards if c.deck_id == deck_id]

        self.tbl_cards.setRowCount(0)
        for c in cards:
            r = self.tbl_cards.rowCount()
            self.tbl_cards.insertRow(r)
            it_f = QTableWidgetItem(c.front)
            it_f.setData(Qt.ItemDataRole.UserRole, c.id)
            it_b = QTableWidgetItem(c.back)
            it_rev = QTableWidgetItem(c.next_review or "Hoje")
            it_int = QTableWidgetItem(f"{c.interval} d")
            self.tbl_cards.setItem(r, 0, it_f)
            self.tbl_cards.setItem(r, 1, it_b)
            self.tbl_cards.setItem(r, 2, it_rev)
            self.tbl_cards.setItem(r, 3, it_int)

    def _on_new_deck(self) -> None:
        name, ok = QInputDialog.getText(None, "Novo Baralho", "Nome do baralho:")
        if ok and name.strip():
            import uuid
            d = Deck(id=str(uuid.uuid4()), name=name.strip())
            self.decks.append(d)
            self._save_data()
            self._refresh_manage_decks()
            self.cmb_manage_deck.setCurrentIndex(len(self.decks) - 1)

    def _on_delete_deck(self) -> None:
        deck_id = self.cmb_manage_deck.currentData()
        if not deck_id:
            return
        reply = QMessageBox.question(
            None,
            "Excluir Baralho",
            "Deseja realmente excluir este baralho e todos os seus cartões?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.decks = [d for d in self.decks if d.id != deck_id]
            self.cards = [c for c in self.cards if c.deck_id != deck_id]
            self._save_data()
            self._refresh_manage_decks()

    def _on_add_card(self) -> None:
        deck_id = self.cmb_manage_deck.currentData()
        if not deck_id:
            QMessageBox.warning(None, "Aviso", "Crie ou selecione um baralho primeiro.")
            return

        dlg = QDialog(None)
        dlg.setWindowTitle("Novo Cartão")
        dlg.resize(400, 250)
        lay = QVBoxLayout(dlg)
        form = QFormLayout()

        txt_f = QTextEdit()
        txt_f.setMaximumHeight(70)
        txt_b = QTextEdit()
        txt_b.setMaximumHeight(70)
        form.addRow("Frente (Pergunta):", txt_f)
        form.addRow("Verso (Resposta):", txt_b)
        lay.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_canc = QPushButton("Cancelar")
        btn_canc.clicked.connect(dlg.reject)
        btn_ok = QPushButton("Salvar")
        btn_ok.setStyleSheet("font-weight: bold; background-color: #0284c7; color: white;")
        btn_ok.clicked.connect(dlg.accept)
        btns.addWidget(btn_canc)
        btns.addWidget(btn_ok)
        lay.addLayout(btns)

        if dlg.exec():
            f_txt = txt_f.toPlainText().strip()
            b_txt = txt_b.toPlainText().strip()
            if f_txt or b_txt:
                import uuid
                c = Flashcard(id=str(uuid.uuid4()), deck_id=deck_id, front=f_txt, back=b_txt)
                self.cards.append(c)
                self._save_data()
                self._refresh_manage_cards()

    def _on_remove_card(self) -> None:
        row = self.tbl_cards.currentRow()
        if row < 0:
            return
        it = self.tbl_cards.item(row, 0)
        if not it:
            return
        card_id = it.data(Qt.ItemDataRole.UserRole)
        self.cards = [c for c in self.cards if c.id != card_id]
        self._save_data()
        self._refresh_manage_cards()

    def _on_import_csv(self) -> None:
        deck_id = self.cmb_manage_deck.currentData()
        if not deck_id:
            return
        path, _ = QFileDialog.getOpenFileName(None, "Importar CSV", "", "CSV (*.csv);;Texto (*.txt)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                imported = import_flashcards_from_csv(content, deck_id)
                self.cards.extend(imported)
                self._save_data()
                self._refresh_manage_cards()
                QMessageBox.information(None, "Sucesso", f"{len(imported)} cartões importados com sucesso!")
            except Exception as e:
                QMessageBox.critical(None, "Erro", f"Falha ao importar CSV:\n{e}")

    def _on_export_csv(self) -> None:
        deck_id = self.cmb_manage_deck.currentData()
        if not deck_id:
            return
        deck_cards = [c for c in self.cards if c.deck_id == deck_id]
        if not deck_cards:
            QMessageBox.warning(None, "Aviso", "O baralho selecionado não possui cartões.")
            return

        path, _ = QFileDialog.getSaveFileName(None, "Exportar CSV", "flashcards.csv", "CSV (*.csv)")
        if path:
            try:
                csv_str = export_flashcards_to_csv(deck_cards)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(csv_str)
                QMessageBox.information(None, "Sucesso", "Cartões exportados com sucesso!")
            except Exception as e:
                QMessageBox.critical(None, "Erro", f"Falha ao exportar CSV:\n{e}")
