"""
Interface de usuário para a ferramenta de Emissão de Recibos e Orçamentos em PDF.
"""
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.productivity.recibo_orcamento.logic import (
    OrcamentoData,
    OrcamentoItem,
    ReciboData,
    generate_orcamento_pdf,
    generate_recibo_pdf,
    numero_para_extenso_reais,
)


@register
class ReciboOrcamentoTool(Tool):
    """Emissor de recibos comerciais e propostas de orçamento em PDF com valor por extenso."""

    id = "productivity.recibo_orcamento"
    name = "Emissor de Recibos e Orçamentos"
    description = "Gere recibos de pagamento e propostas de orçamento em PDF com conversão automática de valores por extenso."
    category = "Produtividade"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("Emissor de Recibos e Orçamentos em PDF")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Crie documentos comerciais prontos para impressão ou envio digital. "
            "Conversão automática de valores em reais por extenso sem necessidade de internet."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Aba 1: Recibo
        tab_recibo = self._build_recibo_tab()
        self.tabs.addTab(tab_recibo, "Recibo de Pagamento")

        # Aba 2: Orçamento
        tab_orcamento = self._build_orcamento_tab()
        self.tabs.addTab(tab_orcamento, "Proposta de Orçamento")

        return widget

    # -------------------------------------------------------------
    # ABA RECIBO
    # -------------------------------------------------------------
    def _build_recibo_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        form = QFormLayout()

        self.txt_recibo_num = QLineEdit(datetime.now().strftime("%Y%m%d01"))
        form.addRow("Número do Recibo:", self.txt_recibo_num)

        # Valor
        val_box = QHBoxLayout()
        self.spn_recibo_val = QDoubleSpinBox()
        self.spn_recibo_val.setRange(0.01, 999999999.99)
        self.spn_recibo_val.setPrefix("R$ ")
        self.spn_recibo_val.setDecimals(2)
        self.spn_recibo_val.setValue(150.00)
        self.spn_recibo_val.valueChanged.connect(self._update_recibo_extenso)
        val_box.addWidget(self.spn_recibo_val)

        self.lbl_recibo_extenso = QLabel()
        self.lbl_recibo_extenso.setStyleSheet("color: #0284c7; font-style: italic;")
        val_box.addWidget(self.lbl_recibo_extenso, 1)
        form.addRow("Valor Nominal:", val_box)

        # Pagador
        self.txt_recibo_pagador = QLineEdit("João da Silva")
        self.txt_recibo_pagador_doc = QLineEdit("123.456.789-00")
        form.addRow("Nome do Pagador (Cliente):", self.txt_recibo_pagador)
        form.addRow("CPF / CNPJ do Pagador:", self.txt_recibo_pagador_doc)

        # Emissor
        self.txt_recibo_emissor = QLineEdit("Maria dos Santos")
        self.txt_recibo_emissor_doc = QLineEdit("987.654.321-99")
        form.addRow("Nome do Emissor (Recebedor):", self.txt_recibo_emissor)
        form.addRow("CPF / CNPJ do Emissor:", self.txt_recibo_emissor_doc)

        # Referente e local
        self.txt_recibo_ref = QLineEdit("Serviços prestados de consultoria técnica e suporte em informática.")
        form.addRow("Referente a:", self.txt_recibo_ref)

        loc_box = QHBoxLayout()
        self.txt_recibo_cidade = QLineEdit("São Paulo - SP")
        self.dt_recibo_data = QDateEdit(QDate.currentDate())
        self.dt_recibo_data.setCalendarPopup(True)
        self.dt_recibo_data.setDisplayFormat("dd/MM/yyyy")
        loc_box.addWidget(self.txt_recibo_cidade, 2)
        loc_box.addWidget(QLabel("Data:"), 0)
        loc_box.addWidget(self.dt_recibo_data, 1)
        form.addRow("Localidade e Data:", loc_box)

        layout.addLayout(form)

        # Botão gerar PDF
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.btn_gerar_recibo = QPushButton("Gerar e Salvar PDF do Recibo")
        self.btn_gerar_recibo.setStyleSheet("font-weight: bold; padding: 8px 16px; background-color: #0284c7; color: white;")
        self.btn_gerar_recibo.clicked.connect(self._on_gerar_recibo)
        btn_box.addWidget(self.btn_gerar_recibo)
        layout.addLayout(btn_box)

        layout.addStretch()
        self._update_recibo_extenso()
        return page

    def _update_recibo_extenso(self) -> None:
        val = self.spn_recibo_val.value()
        extenso = numero_para_extenso_reais(val)
        self.lbl_recibo_extenso.setText(f"({extenso})")

    def _on_gerar_recibo(self) -> None:
        num = self.txt_recibo_num.text().strip() or "001"
        cidade = self.txt_recibo_cidade.text().strip() or "Brasil"
        data_str = self.dt_recibo_data.date().toString("dd 'de' MMMM 'de' yyyy")

        recibo = ReciboData(
            numero=num,
            emissor_nome=self.txt_recibo_emissor.text().strip(),
            emissor_doc=self.txt_recibo_emissor_doc.text().strip(),
            pagador_nome=self.txt_recibo_pagador.text().strip(),
            pagador_doc=self.txt_recibo_pagador_doc.text().strip(),
            valor=self.spn_recibo_val.value(),
            referente=self.txt_recibo_ref.text().strip(),
            cidade=cidade,
            data_emissao=data_str,
        )

        caminho, _ = QFileDialog.getSaveFileName(
            None,
            "Salvar Recibo em PDF",
            f"recibo_{num}.pdf",
            "Documentos PDF (*.pdf)",
        )
        if not caminho:
            return

        try:
            generate_recibo_pdf(recibo, Path(caminho))
            QMessageBox.information(None, "Recibo Gerado", f"Recibo gerado com sucesso em:\n{caminho}")
        except Exception as e:
            QMessageBox.critical(None, "Erro", f"Falha ao gerar PDF do recibo:\n{e}")

    # -------------------------------------------------------------
    # ABA ORÇAMENTO
    # -------------------------------------------------------------
    def _build_orcamento_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        # Informações gerais
        form = QFormLayout()

        num_val_box = QHBoxLayout()
        self.txt_orc_num = QLineEdit(datetime.now().strftime("ORC-%Y%m%d"))
        self.spn_orc_validade = QSpinBox()
        self.spn_orc_validade.setRange(1, 365)
        self.spn_orc_validade.setValue(15)
        self.spn_orc_validade.setSuffix(" dias")
        num_val_box.addWidget(self.txt_orc_num, 2)
        num_val_box.addWidget(QLabel("Validade:"), 0)
        num_val_box.addWidget(self.spn_orc_validade, 1)
        form.addRow("Orçamento Nº:", num_val_box)

        # Prestador
        prest_box = QHBoxLayout()
        self.txt_orc_prest_nome = QLineEdit("Minha Empresa de Serviços LTDA")
        self.txt_orc_prest_doc = QLineEdit("12.345.678/0001-90")
        self.txt_orc_prest_contato = QLineEdit("contato@empresa.com.br | (11) 98765-4321")
        prest_box.addWidget(self.txt_orc_prest_nome, 2)
        prest_box.addWidget(self.txt_orc_prest_doc, 1)
        form.addRow("Prestador / CNPJ:", prest_box)
        form.addRow("Contato do Prestador:", self.txt_orc_prest_contato)

        # Cliente
        cli_box = QHBoxLayout()
        self.txt_orc_cli_nome = QLineEdit("Cliente Exemplo S/A")
        self.txt_orc_cli_doc = QLineEdit("98.765.432/0001-10")
        cli_box.addWidget(self.txt_orc_cli_nome, 2)
        cli_box.addWidget(self.txt_orc_cli_doc, 1)
        form.addRow("Cliente / Documento:", cli_box)

        layout.addLayout(form)

        # Tabela de Itens
        grp_itens = QGroupBox("Itens / Serviços do Orçamento")
        v_itens = QVBoxLayout(grp_itens)

        self.tbl_itens = QTableWidget(0, 4)
        self.tbl_itens.setHorizontalHeaderLabels(["Descrição do Serviço / Produto", "Qtd", "Valor Unit. (R$)", "Total (R$)"])
        self.tbl_itens.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_itens.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_itens.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_itens.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        v_itens.addWidget(self.tbl_itens)

        # Botoes de itens
        item_bar = QHBoxLayout()
        btn_add = QPushButton("Adicionar Item")
        btn_add.clicked.connect(self._add_orc_item)
        btn_del = QPushButton("Remover Item Selecionado")
        btn_del.clicked.connect(self._remove_orc_item)
        item_bar.addWidget(btn_add)
        item_bar.addWidget(btn_del)
        item_bar.addStretch()

        self.lbl_orc_total = QLabel("Total: R$ 0,00")
        self.lbl_orc_total.setStyleSheet("font-size: 15px; font-weight: bold; color: #16a34a;")
        item_bar.addWidget(self.lbl_orc_total)
        v_itens.addLayout(item_bar)

        layout.addWidget(grp_itens)

        # Observações
        obs_box = QVBoxLayout()
        obs_box.addWidget(QLabel("Observações e Condições de Pagamento:"))
        self.txt_orc_obs = QTextEdit(
            "Pagamento: 50% de entrada e 50% na conclusão e homologação dos serviços.\n"
            "Chave Pix: contato@empresa.com.br"
        )
        self.txt_orc_obs.setMaximumHeight(70)
        obs_box.addWidget(self.txt_orc_obs)
        layout.addLayout(obs_box)

        # Botão gerar PDF
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.btn_gerar_orc = QPushButton("Gerar e Salvar PDF do Orçamento")
        self.btn_gerar_orc.setStyleSheet("font-weight: bold; padding: 8px 16px; background-color: #16a34a; color: white;")
        self.btn_gerar_orc.clicked.connect(self._on_gerar_orcamento)
        btn_box.addWidget(self.btn_gerar_orc)
        layout.addLayout(btn_box)

        # Inicializa com 1 item padrão
        self._add_orc_item("Desenvolvimento de Solução Sob Medida", 1.0, 1800.0)

        return page

    def _add_orc_item(self, desc: str = "Novo Item", qtd: float = 1.0, val: float = 100.0) -> None:
        row = self.tbl_itens.rowCount()
        self.tbl_itens.insertRow(row)

        item_desc = QTableWidgetItem(desc)
        item_qtd = QTableWidgetItem(f"{qtd:g}")
        item_qtd.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item_val = QTableWidgetItem(f"{val:.2f}")
        item_val.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        tot = qtd * val
        item_tot = QTableWidgetItem(f"R$ {tot:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        item_tot.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item_tot.setFlags(item_tot.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.tbl_itens.setItem(row, 0, item_desc)
        self.tbl_itens.setItem(row, 1, item_qtd)
        self.tbl_itens.setItem(row, 2, item_val)
        self.tbl_itens.setItem(row, 3, item_tot)

        self.tbl_itens.cellChanged.connect(self._on_cell_changed)
        self._recalc_orc_total()

    def _remove_orc_item(self) -> None:
        cur_row = self.tbl_itens.currentRow()
        if cur_row >= 0:
            self.tbl_itens.removeRow(cur_row)
            self._recalc_orc_total()

    def _on_cell_changed(self, row: int, col: int) -> None:
        if col in (1, 2):
            try:
                self.tbl_itens.blockSignals(True)
                qtd_str = self.tbl_itens.item(row, 1).text().replace(",", ".") if self.tbl_itens.item(row, 1) else "1"
                val_str = self.tbl_itens.item(row, 2).text().replace("R$", "").replace(" ", "").replace(",", ".") if self.tbl_itens.item(row, 2) else "0"
                qtd = float(qtd_str)
                val = float(val_str)
                tot = qtd * val
                tot_item = self.tbl_itens.item(row, 3)
                if tot_item:
                    tot_item.setText(f"R$ {tot:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            except Exception:
                pass
            finally:
                self.tbl_itens.blockSignals(False)
            self._recalc_orc_total()

    def _recalc_orc_total(self) -> None:
        total = 0.0
        for r in range(self.tbl_itens.rowCount()):
            try:
                qtd_str = self.tbl_itens.item(r, 1).text().replace(",", ".") if self.tbl_itens.item(r, 1) else "0"
                val_str = self.tbl_itens.item(r, 2).text().replace("R$", "").replace(" ", "").replace(",", ".") if self.tbl_itens.item(r, 2) else "0"
                total += float(qtd_str) * float(val_str)
            except Exception:
                continue
        tot_fmt = f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        self.lbl_orc_total.setText(f"Total: {tot_fmt}")

    def _on_gerar_orcamento(self) -> None:
        itens = []
        for r in range(self.tbl_itens.rowCount()):
            desc = self.tbl_itens.item(r, 0).text() if self.tbl_itens.item(r, 0) else "Item"
            try:
                qtd = float(self.tbl_itens.item(r, 1).text().replace(",", "."))
                val = float(self.tbl_itens.item(r, 2).text().replace("R$", "").replace(" ", "").replace(",", "."))
            except Exception:
                qtd = 1.0
                val = 0.0
            itens.append(OrcamentoItem(descricao=desc, quantidade=qtd, valor_unitario=val))

        if not itens:
            QMessageBox.warning(None, "Aviso", "Adicione pelo menos um item ao orçamento.")
            return

        orc = OrcamentoData(
            numero=self.txt_orc_num.text().strip() or "ORC-001",
            emissor_nome=self.txt_orc_prest_nome.text().strip(),
            emissor_doc=self.txt_orc_prest_doc.text().strip(),
            emissor_contato=self.txt_orc_prest_contato.text().strip(),
            cliente_nome=self.txt_orc_cli_nome.text().strip(),
            cliente_doc=self.txt_orc_cli_doc.text().strip(),
            data_emissao=datetime.now().strftime("%d/%m/%Y"),
            validade_dias=self.spn_orc_validade.value(),
            itens=itens,
            observacoes=self.txt_orc_obs.toPlainText().strip(),
        )

        caminho, _ = QFileDialog.getSaveFileName(
            None,
            "Salvar Orçamento em PDF",
            f"{orc.numero}.pdf",
            "Documentos PDF (*.pdf)",
        )
        if not caminho:
            return

        try:
            generate_orcamento_pdf(orc, Path(caminho))
            QMessageBox.information(None, "Orçamento Gerado", f"Orçamento gerado com sucesso em:\n{caminho}")
        except Exception as e:
            QMessageBox.critical(None, "Erro", f"Falha ao gerar PDF do orçamento:\n{e}")
