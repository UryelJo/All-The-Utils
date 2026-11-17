"""
Ferramenta: Ferramentas e Manutenção do Windows (Central Unificada).
Integra:
  1. Manutenção e Central de Reparos (SFC, DISM, Defrag, Temp, DNS, Rede, Spooler, Ícones, Windows Update, Store)
  2. Ajustes Rápidos do Windows e Menu de Contexto do Windows 11
  3. Controle de Sessão: Manter Sistema Acordado (Keep Awake) e Agendador de Desligamento/Ações
"""
from typing import Any, Callable, Optional
from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QRadioButton, QScrollArea,
    QSpinBox, QTabWidget, QTimeEdit, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin, prompt_elevation_dialog, request_elevation
from wintoolbox.core.registry import Tool, ToolResult, register
from wintoolbox.core.shell import run_command_streaming
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.system.context_menu.logic import (
    is_classic_context_menu_enabled, restart_explorer, set_classic_context_menu
)
from wintoolbox.tools.system.keep_awake.tool import KeepAwakeTool
from wintoolbox.tools.system.power_manager.logic import (
    cancel_scheduled_shutdown, schedule_system_action
)
from wintoolbox.tools.system.quick_tweaks.logic import (
    apply_quick_tweak, get_quick_tweaks_state, restart_windows_explorer
)
from wintoolbox.tools.system.repair_center.logic import (
    clear_icon_and_thumbnail_cache, flush_network_stack,
    repair_print_spooler, reset_microsoft_store, reset_windows_update
)
from wintoolbox.tools.system.tools.logic import clean_temp_directory
from wintoolbox.ui.theme import get_current_tokens
from wintoolbox.ui.widgets.log_panel import LogPanelWidget
from wintoolbox.ui.widgets.toast import show_toast


@register
class SystemToolsTool(Tool):
    id = "system.tools"
    name = "Ferramentas do Windows"
    category = "Sistema"
    description = (
        "Central de reparos, limpeza de cache DNS/temporários, ajustes rápidos, "
        "menu de contexto do Windows 11, manter acordado e agendamento do sistema"
    )
    keywords = [
        "sistema", "manutenção", "disco", "sfc", "defrag", "dns", "temp", "limpeza",
        "reparo", "spooler", "windows update", "store", "tweaks", "ocultos", "extensão",
        "menu de contexto", "windows 11", "awake", "acordado", "desligar", "agendar"
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return SystemToolsView(self, parent)


class SystemToolsView(QWidget):
    def __init__(self, tool: SystemToolsTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self._keep_awake_tool = KeepAwakeTool()
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 16)
        root_layout.setSpacing(10)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setProperty("class", "title")
        root_layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setProperty("class", "secondary")
        root_layout.addWidget(lbl_desc)

        # Alerta de privilégios de Administrador
        admin_card = QFrame()
        admin_card.setProperty("class", "card")
        admin_layout = QHBoxLayout(admin_card)
        admin_layout.setContentsMargins(12, 8, 12, 8)

        admin_status = "Executando como Administrador" if is_admin() else "Executando como Usuário Padrão"
        self.lbl_admin = QLabel(f"Status UAC: {admin_status}")
        self.lbl_admin.setStyleSheet("font-weight: 500; background: transparent;")
        admin_layout.addWidget(self.lbl_admin)
        admin_layout.addStretch()

        if not is_admin():
            btn_elevate = QPushButton("Executar como Administrador")
            btn_elevate.clicked.connect(self._on_elevate)
            admin_layout.addWidget(btn_elevate)

        root_layout.addWidget(admin_card)

        # Abas organizadas
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_repairs_tab(), "Manutenção e Central de Reparos")
        self.tabs.addTab(self._build_tweaks_tab(), "Ajustes Rápidos e Menu de Contexto")
        self.tabs.addTab(self._build_session_tab(), "Manter Acordado e Agendar Desligamento")
        root_layout.addWidget(self.tabs, stretch=1)

    # =========================================================================
    # ABA 1: MANUTENÇÃO E CENTRAL DE REPAROS
    # =========================================================================
    def _build_repairs_tab(self) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(4, 8, 4, 4)
        tab_layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        c_lay = QVBoxLayout(content)
        c_lay.setContentsMargins(0, 0, 4, 0)
        c_lay.setSpacing(10)

        # Card 1: Comandos Diretos de Manutenção e Limpeza
        grp_maint = QGroupBox("Diagnóstico, Limpeza e Integridade do Sistema")
        grid_layout = QGridLayout(grp_maint)
        grid_layout.setContentsMargins(12, 12, 12, 12)
        grid_layout.setSpacing(10)

        btn_sfc = QPushButton("Verificar Integridade de Arquivos (SFC /scannow)")
        btn_sfc.clicked.connect(lambda: self._run_command("sfc /scannow", requires_admin=True))
        grid_layout.addWidget(btn_sfc, 0, 0)

        btn_dism = QPushButton("Reparar Imagem do Windows (DISM /RestoreHealth)")
        btn_dism.clicked.connect(
            lambda: self._run_command("DISM.exe /Online /Cleanup-Image /RestoreHealth", requires_admin=True)
        )
        grid_layout.addWidget(btn_dism, 0, 1)

        btn_defrag = QPushButton("Otimizar e Desfragmentar Unidade C:")
        btn_defrag.clicked.connect(lambda: self._run_command("defrag C: /O", requires_admin=True))
        grid_layout.addWidget(btn_defrag, 1, 0)

        btn_temp = QPushButton("Limpar Arquivos Temporários (%TEMP%)")
        btn_temp.clicked.connect(self._run_clean_temp)
        grid_layout.addWidget(btn_temp, 1, 1)

        btn_dns = QPushButton("Limpar Cache de DNS (ipconfig /flushdns)")
        btn_dns.clicked.connect(lambda: self._run_command("ipconfig /flushdns", requires_admin=False))
        grid_layout.addWidget(btn_dns, 2, 0)

        btn_net_reset = QPushButton("Redefinir Pilha de Rede Completa (Winsock + TCP/IP + DNS)")
        btn_net_reset.clicked.connect(
            lambda: self._execute_repair("Redefinir Pilha de Rede e Cache DNS", flush_network_stack, requires_admin=True)
        )
        grid_layout.addWidget(btn_net_reset, 2, 1)

        c_lay.addWidget(grp_maint)

        # Card 2: Central de Reparos Automatizados
        grp_repairs = QGroupBox("Central de Reparos de Serviços e Caches do Windows")
        rep_lay = QVBoxLayout(grp_repairs)
        rep_lay.setContentsMargins(12, 12, 12, 12)
        rep_lay.setSpacing(8)

        repairs = [
            (
                "Destravar Fila de Impressão (Spooler)",
                "Interrompe o serviço de spooler, remove documentos presos em buffer e reinicia o serviço.",
                repair_print_spooler,
                True,
            ),
            (
                "Reconstruir Cache de Ícones e Miniaturas",
                "Corrige ícones brancos, genéricos ou miniaturas corrompidas reiniciando o cache do Explorer.",
                clear_icon_and_thumbnail_cache,
                False,
            ),
            (
                "Resetar Componentes do Windows Update",
                "Para serviços de atualização e limpa pacotes corrompidos em SoftwareDistribution.",
                reset_windows_update,
                True,
            ),
            (
                "Redefinir Cache da Microsoft Store (wsreset)",
                "Limpa o cache corrompido da Microsoft Store que impede download ou atualização de apps.",
                reset_microsoft_store,
                False,
            ),
        ]

        for title, desc, fn, req_adm in repairs:
            row_frame = QFrame()
            row_frame.setProperty("class", "card")
            row_lay = QHBoxLayout(row_frame)
            row_lay.setContentsMargins(12, 8, 12, 8)
            row_lay.setSpacing(10)

            text_lay = QVBoxLayout()
            text_lay.setSpacing(2)
            lbl_t = QLabel(f"<b>{title}</b>")
            lbl_d = QLabel(desc)
            lbl_d.setProperty("class", "secondary")
            lbl_d.setWordWrap(True)
            text_lay.addWidget(lbl_t)
            text_lay.addWidget(lbl_d)
            row_lay.addLayout(text_lay, stretch=1)

            btn = QPushButton("Executar Reparo")
            btn.setProperty("accent", True)
            btn.setFixedWidth(140)
            btn.clicked.connect(lambda _, f=fn, t=title, adm=req_adm: self._execute_repair(t, f, requires_admin=adm))
            row_lay.addWidget(btn)

            rep_lay.addWidget(row_frame)

        c_lay.addWidget(grp_repairs)
        c_lay.addStretch()
        scroll.setWidget(content)
        tab_layout.addWidget(scroll, stretch=1)

        self.log_panel = LogPanelWidget(title="Log de Execução de Manutenção e Reparos")
        self.log_panel.setMaximumHeight(150)
        tab_layout.addWidget(self.log_panel)
        return tab

    # =========================================================================
    # ABA 2: AJUSTES RÁPIDOS E MENU DE CONTEXTO DO WINDOWS 11
    # =========================================================================
    def _build_tweaks_tab(self) -> QWidget:
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(12)

        # Card 1: Explorador de Arquivos
        grp_explorer = QGroupBox("Ajustes Rápidos — Explorador de Arquivos e Área de Trabalho")
        exp_layout = QVBoxLayout(grp_explorer)
        exp_layout.setSpacing(8)

        self.chk_hidden = QCheckBox("Exibir arquivos, pastas e unidades ocultas no Windows")
        exp_layout.addWidget(self.chk_hidden)

        self.chk_extensions = QCheckBox("Exibir extensões de tipos de arquivo conhecidos (.exe, .txt, .pdf, etc.)")
        exp_layout.addWidget(self.chk_extensions)

        self.chk_this_pc = QCheckBox("Exibir o ícone 'Este Computador' na Área de Trabalho")
        exp_layout.addWidget(self.chk_this_pc)

        self.chk_recent = QCheckBox("Ocultar arquivos recentes e pastas frequentes no Acesso Rápido")
        exp_layout.addWidget(self.chk_recent)

        layout.addWidget(grp_explorer)

        # Card 2: Aparência e Modo Escuro
        grp_theme = QGroupBox("Ajustes Rápidos — Aparência e Cores do Sistema")
        thm_layout = QVBoxLayout(grp_theme)
        thm_layout.setSpacing(8)

        self.chk_dark_apps = QCheckBox("Modo Escuro para Aplicativos do Windows")
        thm_layout.addWidget(self.chk_dark_apps)

        self.chk_dark_sys = QCheckBox("Modo Escuro para o Sistema Operacional (Barra de Tarefas e Menu Iniciar)")
        thm_layout.addWidget(self.chk_dark_sys)

        btn_bar = QHBoxLayout()
        self.btn_apply_tweaks = QPushButton("Aplicar Ajustes Rápidos")
        self.btn_apply_tweaks.setProperty("class", "primary")
        self.btn_apply_tweaks.clicked.connect(self._on_apply_tweaks)
        btn_bar.addWidget(self.btn_apply_tweaks)

        self.btn_reload_tweaks = QPushButton("Recarregar Estado Atual")
        self.btn_reload_tweaks.clicked.connect(self._load_quick_tweaks_state)
        btn_bar.addWidget(self.btn_reload_tweaks)

        self.btn_restart_exp = QPushButton("Reiniciar Windows Explorer")
        self.btn_restart_exp.clicked.connect(self._on_restart_explorer)
        btn_bar.addWidget(self.btn_restart_exp)

        btn_bar.addStretch()
        thm_layout.addLayout(btn_bar)
        layout.addWidget(grp_theme)

        # Card 3: Menu de Contexto do Windows 11
        grp_ctx = QGroupBox("Menu de Contexto do Windows 11 (Botão Direito no Explorer)")
        ctx_layout = QVBoxLayout(grp_ctx)
        ctx_layout.setSpacing(8)

        self.lbl_ctx_mode = QLabel()
        self.lbl_ctx_mode.setStyleSheet("font-size: 14px; font-weight: bold;")
        ctx_layout.addWidget(self.lbl_ctx_mode)

        self.lbl_ctx_desc = QLabel()
        self.lbl_ctx_desc.setProperty("class", "secondary")
        self.lbl_ctx_desc.setWordWrap(True)
        ctx_layout.addWidget(self.lbl_ctx_desc)

        ctx_btn_row = QHBoxLayout()
        self.btn_enable_classic = QPushButton("Ativar Menu Clássico Completo (Sem 'Mostrar mais opções')")
        self.btn_enable_classic.setProperty("accent", True)
        self.btn_enable_classic.clicked.connect(lambda: self._apply_context_menu(True))
        ctx_btn_row.addWidget(self.btn_enable_classic)

        self.btn_restore_modern = QPushButton("Restaurar Menu Moderno Padrão do Windows 11")
        self.btn_restore_modern.clicked.connect(lambda: self._apply_context_menu(False))
        ctx_btn_row.addWidget(self.btn_restore_modern)
        ctx_btn_row.addStretch()
        ctx_layout.addLayout(ctx_btn_row)

        self.chk_ctx_restart = QCheckBox("Reiniciar o Windows Explorer automaticamente ao alternar o menu")
        self.chk_ctx_restart.setChecked(True)
        ctx_layout.addWidget(self.chk_ctx_restart)

        layout.addWidget(grp_ctx)
        layout.addStretch()

        scroll.setWidget(content)
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._load_quick_tweaks_state()
        self._refresh_context_menu_ui()
        return tab

    # =========================================================================
    # ABA 3: MANTER ACORDADO E AGENDADOR DE AÇÕES DO SISTEMA
    # =========================================================================
    def _build_session_tab(self) -> QWidget:
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(14)

        # Card 1: Manter Sistema Acordado (Keep Awake)
        grp_awake = QGroupBox("Manter Sistema Acordado (Impedir Suspensão e Desligamento de Tela)")
        awake_lay = QVBoxLayout(grp_awake)
        awake_lay.addWidget(self._keep_awake_tool.build_ui())
        layout.addWidget(grp_awake)

        # Card 2: Agendar Ação do Sistema (Desligar, Reiniciar, Suspender, Bloquear)
        grp_timer = QGroupBox("Agendar Ação do Sistema (Temporizador de Desligamento / Reinício)")
        timer_layout = QVBoxLayout(grp_timer)
        timer_layout.setSpacing(10)

        row_act = QHBoxLayout()
        row_act.addWidget(QLabel("Ação a Executar:"))
        self.cmb_action = QComboBox()
        self.cmb_action.addItem("Desligar o Computador", "shutdown")
        self.cmb_action.addItem("Reiniciar o Computador", "restart")
        self.cmb_action.addItem("Suspender (Sleep)", "sleep")
        self.cmb_action.addItem("Bloquear Estação de Trabalho", "lock")
        row_act.addWidget(self.cmb_action, 1)
        timer_layout.addLayout(row_act)

        self.rb_timer = QRadioButton("Executar daqui a:")
        self.rb_timer.setChecked(True)
        self.rb_time = QRadioButton("Executar no horário exato:")

        row_spin = QHBoxLayout()
        row_spin.addWidget(self.rb_timer)
        self.spin_minutes = QSpinBox()
        self.spin_minutes.setRange(1, 1440)
        self.spin_minutes.setValue(30)
        self.spin_minutes.setSuffix(" minutos")
        row_spin.addWidget(self.spin_minutes)
        row_spin.addStretch()
        timer_layout.addLayout(row_spin)

        row_clock = QHBoxLayout()
        row_clock.addWidget(self.rb_time)
        self.time_edit = QTimeEdit()
        self.time_edit.setTime(QTime.currentTime().addSecs(3600))
        row_clock.addWidget(self.time_edit)
        row_clock.addStretch()
        timer_layout.addLayout(row_clock)

        btn_row = QHBoxLayout()
        self.btn_schedule = QPushButton("Agendar Ação Agora")
        self.btn_schedule.setProperty("class", "primary")
        self.btn_schedule.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self.btn_schedule.clicked.connect(self._on_schedule_action)
        btn_row.addWidget(self.btn_schedule)

        self.btn_cancel_sched = QPushButton("Cancelar Agendamento Ativo")
        self.btn_cancel_sched.clicked.connect(self._on_cancel_action)
        btn_row.addWidget(self.btn_cancel_sched)
        btn_row.addStretch()
        timer_layout.addLayout(btn_row)

        layout.addWidget(grp_timer)
        layout.addStretch()

        scroll.setWidget(content)
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return tab

    # =========================================================================
    # HANDLERS
    # =========================================================================
    def _on_elevate(self):
        if request_elevation():
            self.lbl_admin.setText("Reiniciando com elevação...")

    def _run_clean_temp(self):
        self.log_panel.append_log("INFO", "Iniciando limpeza de arquivos temporários...")

        def worker(ctx):
            clean_temp_directory(lambda msg: ctx.on_log("INFO", msg))
            return ToolResult(success=True, message="Limpeza concluída.")

        self.runner.start_task(
            task_fn=worker,
            on_log=lambda lvl, msg: self.log_panel.append_log(lvl, msg),
        )

    def _run_command(self, cmd_str: str, requires_admin: bool = False):
        if requires_admin and not is_admin():
            prompt_elevation_dialog(
                self,
                tool_name=self.tool.name,
                reason=f"O comando '{cmd_str}' necessita de privilégios de Administrador.",
            )
            return

        self.log_panel.append_log("INFO", f"Executando comando: {cmd_str}")

        def worker(ctx):
            code = run_command_streaming(
                cmd=cmd_str,
                on_output=lambda line: ctx.on_log("INFO", line),
                shell=True,
                is_cancelled=ctx.is_cancelled,
            )
            return ToolResult(
                success=(code == 0),
                message=f"Comando finalizado com código de retorno: {code}",
            )

        self.runner.start_task(
            task_fn=worker,
            on_log=lambda lvl, msg: self.log_panel.append_log(lvl, msg),
        )

    def _execute_repair(self, name: str, func: Callable[[], Any], requires_admin: bool = False) -> None:
        if requires_admin and not is_admin():
            prompt_elevation_dialog(
                self,
                tool_name=self.tool.name,
                reason=f"O reparo '{name}' requer privilégios de Administrador.",
            )
            return

        self.log_panel.append_line(f"Iniciando: {name}...")

        def _worker():
            return func()

        def _on_done(result):
            success, msg = result
            if success:
                self.log_panel.append_line(f"Sucesso: {msg}\n")
                show_toast(self, "Reparo concluído com sucesso!")
            else:
                self.log_panel.append_line(f"Aviso/Falha: {msg}\n")
                show_toast(self, msg, is_error=True)

        def _on_error(err):
            self.log_panel.append_line(f"Erro: {err}\n")
            show_toast(self, f"Erro: {err}", is_error=True)

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)

    def _load_quick_tweaks_state(self):
        st = get_quick_tweaks_state()
        self.chk_hidden.setChecked(st.get("show_hidden_files", False))
        self.chk_extensions.setChecked(st.get("show_file_extensions", False))
        self.chk_this_pc.setChecked(st.get("show_this_pc_desktop", False))
        self.chk_recent.setChecked(st.get("hide_quick_access_recent", False))
        self.chk_dark_apps.setChecked(st.get("dark_mode_apps", True))
        self.chk_dark_sys.setChecked(st.get("dark_mode_system", True))

    def _on_apply_tweaks(self):
        targets = [
            ("show_hidden_files", self.chk_hidden.isChecked()),
            ("show_file_extensions", self.chk_extensions.isChecked()),
            ("show_this_pc_desktop", self.chk_this_pc.isChecked()),
            ("hide_quick_access_recent", self.chk_recent.isChecked()),
            ("dark_mode_apps", self.chk_dark_apps.isChecked()),
            ("dark_mode_system", self.chk_dark_sys.isChecked()),
        ]
        errors = []
        for tweak_id, val in targets:
            ok, msg = apply_quick_tweak(tweak_id, val)
            if not ok:
                errors.append(msg)

        if not errors:
            ans = QMessageBox.question(
                self,
                "Ajustes Aplicados",
                "Todos os ajustes selecionados foram gravados no registro!\n\n"
                "Deseja reiniciar o Windows Explorer agora para atualizar as janelas?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if ans == QMessageBox.Yes:
                self._on_restart_explorer()
        else:
            QMessageBox.warning(self, "Aviso", "Alguns ajustes falharam:\n" + "\n".join(errors))

    def _on_restart_explorer(self):
        ok, msg = restart_windows_explorer()
        if ok:
            show_toast(self, msg)
        else:
            QMessageBox.critical(self, "Erro", msg)

    def _refresh_context_menu_ui(self):
        is_classic = is_classic_context_menu_enabled()
        t = get_current_tokens()
        if is_classic:
            self.lbl_ctx_mode.setText("Status Atual: Menu Clássico Completo (Estilo Windows 10)")
            self.lbl_ctx_mode.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {t.status_success};")
            self.lbl_ctx_desc.setText(
                "Todas as opções aparecem diretamente ao clicar com o botão direito, sem precisar clicar em 'Mostrar mais opções'."
            )
            self.btn_enable_classic.setEnabled(False)
            self.btn_restore_modern.setEnabled(True)
        else:
            self.lbl_ctx_mode.setText("Status Atual: Menu Moderno Padrão (Estilo Windows 11)")
            self.lbl_ctx_mode.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {t.accent};")
            self.lbl_ctx_desc.setText(
                "Menu compacto do Windows 11 com ícones rápidos e opção 'Mostrar mais opções'."
            )
            self.btn_enable_classic.setEnabled(True)
            self.btn_restore_modern.setEnabled(False)

    def _apply_context_menu(self, enable_classic: bool):
        ok, msg = set_classic_context_menu(enable_classic)
        if ok:
            show_toast(self, msg)
            if self.chk_ctx_restart.isChecked():
                restart_explorer()
            self._refresh_context_menu_ui()
        else:
            show_toast(self, msg, is_error=True)

    def _on_schedule_action(self):
        action = self.cmb_action.currentData()
        if self.rb_timer.isChecked():
            delay_sec = self.spin_minutes.value() * 60
        else:
            now = QTime.currentTime()
            target = self.time_edit.time()
            sec_diff = now.secsTo(target)
            if sec_diff <= 0:
                sec_diff += 86400
            delay_sec = sec_diff

        ok, msg = schedule_system_action(action, delay_sec)
        if ok:
            QMessageBox.information(self, "Agendamento do Sistema", msg)
        else:
            QMessageBox.critical(self, "Erro", msg)

    def _on_cancel_action(self):
        ok, msg = cancel_scheduled_shutdown()
        if ok:
            QMessageBox.information(self, "Cancelado", msg)
        else:
            QMessageBox.warning(self, "Aviso", msg)
