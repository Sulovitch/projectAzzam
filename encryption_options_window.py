from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QComboBox, QMessageBox, QDialog, QDialogButtonBox
import os
from encrypt_window import EncryptHelper
from urllib.parse import quote, unquote

class EncryptionOptionsWindow(QWidget):
    def __init__(self, file_path, username, user_id, s3_client, s3_bucket, db_connection):
        super().__init__()
        self.setWindowTitle("Encryption Options")
        self.file_path = file_path
        self.username = username
        self.user_id = user_id
        self.s3_client = s3_client
        self.s3_bucket = s3_bucket
        self.db_connection = db_connection

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        file_name = os.path.basename(self.file_path)
        layout.addWidget(QLabel(f"Selected file: {file_name}"))

        # زر تشفير
        self.encrypt_btn = QPushButton("تشفير")
        self.encrypt_btn.clicked.connect(self.handle_encryption)
        layout.addWidget(self.encrypt_btn)

        # زر تشفير متقدم
        self.advanced_btn = QPushButton("تشفير متقدم")
        self.advanced_btn.clicked.connect(self.handle_advanced_encryption)
        layout.addWidget(self.advanced_btn)

        self.setLayout(layout)

    def handle_encryption(self):
        # تشفير تلقائي حسب نوع الملف
        ext = os.path.splitext(self.file_path)[1].lower()
        file_type = EncryptHelper.get_file_type_from_extension(ext)
        if file_type == "image":
            encryption_type = "AES"
        elif file_type == "video":
            encryption_type = "ChaCha20"
        else:
            encryption_type = "Blowfish"

        self.encrypt_file(encryption_type)

    def handle_advanced_encryption(self):
        # عرض خيارات التشفير المتقدم (AES، ChaCha20، Blowfish)
        dialog = self.show_advanced_encryption_dialog()
        if dialog.result() == QDialog.Accepted:
            encryption_type = dialog.selected_encryption
            self.encrypt_file(encryption_type)

    def show_advanced_encryption_dialog(self):
        # إنشاء نافذة منبثقة لاختيار نوع التشفير المتقدم
        dialog = QDialog(self)
        dialog.setWindowTitle("اختر خوارزمية التشفير")

        layout = QVBoxLayout(dialog)

        combo_box = QComboBox(dialog)
        combo_box.addItems([
            "AES",
            "ChaCha20",
            "Blowfish"
        ])
        layout.addWidget(combo_box)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        layout.addWidget(button_box)

        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)

        dialog.selected_encryption = None

        # بعد قبول الاختيار
        def set_encryption():
            dialog.selected_encryption = combo_box.currentText()

        button_box.accepted.connect(set_encryption)

        dialog.exec_()

        return dialog

    def encrypt_file(self, encryption_type):
        try:
            # ترميز اسم الملف عند بناء المفتاح
            s3_key = f"user_{self.user_id}/{quote(self.file_path)}"
            EncryptHelper.encrypt_file(
                self.file_path,
                encryption_type,
                self.username,
                self.user_id,
                self.s3_client,
                self.s3_bucket,
                self.db_connection
            )
            QMessageBox.information(self, "نجاح", f"تم تشفير ورفع الملف باستخدام {encryption_type} بنجاح.")
            self.close()
        except Exception as e:
            QMessageBox.critical(self, "خطأ", str(e))
