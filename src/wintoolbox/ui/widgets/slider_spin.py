"""
Widget de controle numérico combinado: QSlider + QSpinBox / QDoubleSpinBox sincronizados.
Oferece ajuste visual rápido com slider e entrada exata com teclado ou setas.
"""
from typing import Optional, Union
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox, QHBoxLayout, QLabel, QSlider, QSpinBox, QWidget
)


class SliderSpinControl(QWidget):
    """
    Controle sincronizado Slider + SpinBox.
    Suporta inteiros e decimais (se decimals > 0, usa QDoubleSpinBox).
    """
    valueChanged = Signal(object)  # emite int ou float

    def __init__(
        self,
        label: str = "",
        min_value: Union[int, float] = 0,
        max_value: Union[int, float] = 100,
        initial_value: Union[int, float] = 50,
        step: Union[int, float] = 1,
        decimals: int = 0,
        suffix: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._decimals = decimals
        self._multiplier = 10 ** decimals if decimals > 0 else 1
        self._step = step

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        if label:
            self._lbl = QLabel(label, self)
            self._lbl.setStyleSheet("font-weight: 500;")
            layout.addWidget(self._lbl)
        else:
            self._lbl = None

        self._slider = QSlider(Qt.Orientation.Horizontal, self)
        self._slider.setRange(int(min_value * self._multiplier), int(max_value * self._multiplier))
        self._slider.setSingleStep(int(step * self._multiplier))
        layout.addWidget(self._slider, stretch=1)

        if decimals > 0:
            self._spin: Union[QSpinBox, QDoubleSpinBox] = QDoubleSpinBox(self)
            self._spin.setDecimals(decimals)
            self._spin.setRange(float(min_value), float(max_value))
            self._spin.setSingleStep(float(step))
        else:
            self._spin = QSpinBox(self)
            self._spin.setRange(int(min_value), int(max_value))
            self._spin.setSingleStep(int(step))

        if suffix:
            self._spin.setSuffix(suffix)

        self._spin.setFixedWidth(78 if suffix else 68)
        layout.addWidget(self._spin)

        # Sincronização segura
        self._slider.valueChanged.connect(self._on_slider_changed)
        self._spin.valueChanged.connect(self._on_spin_changed)

        self.setValue(initial_value)

    def _on_slider_changed(self, val: int) -> None:
        if self._decimals > 0:
            real_val = round(val / self._multiplier, self._decimals)
        else:
            real_val = val

        self._spin.blockSignals(True)
        self._spin.setValue(real_val)
        self._spin.blockSignals(False)
        self.valueChanged.emit(real_val)

    def _on_spin_changed(self, val: Union[int, float]) -> None:
        if self._decimals > 0:
            slider_val = int(round(val * self._multiplier))
        else:
            slider_val = int(val)

        self._slider.blockSignals(True)
        self._slider.setValue(slider_val)
        self._slider.blockSignals(False)
        self.valueChanged.emit(val)

    def value(self) -> Union[int, float]:
        return self._spin.value()

    def setValue(self, val: Union[int, float]) -> None:
        self._spin.setValue(val)
        # aciona o sincronismo
        if self._decimals > 0:
            self._slider.setValue(int(round(val * self._multiplier)))
        else:
            self._slider.setValue(int(val))

    def setRange(self, min_val: Union[int, float], max_val: Union[int, float]) -> None:
        self._slider.setRange(int(min_val * self._multiplier), int(max_val * self._multiplier))
        self._spin.setRange(min_val, max_val)

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        self._slider.setEnabled(enabled)
        self._spin.setEnabled(enabled)
        if self._lbl:
            self._lbl.setEnabled(enabled)

