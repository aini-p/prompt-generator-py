# src/widgets/generation_options_dialog.py
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QSpinBox,
    QDialogButtonBox,
    QLabel,
)
from typing import Tuple


class GenerationOptionsDialog(QDialog):
    """
    画像生成実行前に Batch Size, Iterations, Seed を指定するダイアログ。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generation Options")
        self.setModal(True)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setMinimum(1)
        self.batch_size_spin.setMaximum(16)  # 妥当な最大値
        self.batch_size_spin.setValue(2)
        self.batch_size_spin.setToolTip("一度に生成する画像の枚数 (Batch Size)")

        self.n_iter_spin = QSpinBox()
        self.n_iter_spin.setMinimum(1)
        self.n_iter_spin.setMaximum(100)  # 妥当な最大値
        self.n_iter_spin.setValue(1)
        self.n_iter_spin.setToolTip(
            "バッチ処理を繰り返す回数 (Batch Count / Iterations)"
        )

        self.seed_spin = QSpinBox()
        self.seed_spin.setMinimum(-1)
        self.seed_spin.setMaximum(2**31 - 1)
        self.seed_spin.setValue(-1)
        self.seed_spin.setToolTip("シード値 (-1でランダム)")

        form_layout.addRow("Batch Size:", self.batch_size_spin)
        form_layout.addRow("Batch Iterations (n_iter):", self.n_iter_spin)
        form_layout.addRow("Seed Override:", self.seed_spin)

        layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_values(self) -> Tuple[int, int, int]:
        """
        ダイアログで設定された値を (batch_size, n_iter, seed) のタプルとして返します。
        """
        return (
            self.batch_size_spin.value(),
            self.n_iter_spin.value(),
            self.seed_spin.value(),
        )
