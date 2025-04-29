import os
import tempfile
import json
import re
from urllib.parse import quote
from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QListWidgetItem
from Crypto.Cipher import AES, Blowfish
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from mysql.connector import Error

class DecryptWindow(QObject):
    def __init__(self, filename, username, user_id, s3_client, s3_bucket, db_connection,
                 uploaded_list, decrypted_list):
        super().__init__()
        self.filename = filename
        self.username = username
        self.user_id = user_id
        self.s3_client = s3_client
        self.s3_bucket = s3_bucket
        self.db_connection = db_connection
        self.uploaded_list = uploaded_list
        self.decrypted_list = decrypted_list

        self.decrypt_file()

    def decrypt_file(self):
        try:
            if not (is_video_file(self.filename) or is_image_file(self.filename) or is_document_file(self.filename)):
                QMessageBox.critical(None, "Error", "The selected file is not a valid supported file type (video, image, or document).")
                return

            safe_filename = normalize_filename(self.filename)
            temp_path = os.path.join(tempfile.gettempdir(), safe_filename)
            s3_key = f"user_{self.user_id}/{self.filename}"

            print(f"[DECRYPT] Attempting to download file with key: {s3_key}")
            self.s3_client.download_file(self.s3_bucket, s3_key, temp_path)

            cursor = self.db_connection.cursor(dictionary=True, buffered=True)
            encryption_id = None
            table_map = {
                "file": "FileName",
                "image": "ImageName",
                "video": "VideoName"
            }

            for table, column in table_map.items():
                cursor.execute(f"SELECT EncryptionID FROM {table} WHERE {column} = %s", (self.filename,))
                result = cursor.fetchone()
                if result:
                    encryption_id = result['EncryptionID']
                    break

            if not encryption_id:
                QMessageBox.critical(None, "خطأ", "لم يتم العثور على التشفير في قاعدة البيانات.")
                return

            cursor.execute("SELECT EncryptionType, EncryptionKey, IV FROM encryptionmethod WHERE EncryptionID = %s", (encryption_id,))
            enc_info = cursor.fetchone()
            cursor.close()

            if not enc_info:
                QMessageBox.critical(None, "خطأ", "تعذر جلب بيانات التشفير.")
                return

            encryption_type = enc_info['EncryptionType']
            key = bytes.fromhex(enc_info['EncryptionKey'])
            iv = bytes.fromhex(enc_info['IV']) if enc_info['IV'] else None

            with open(temp_path, 'rb') as f:
                ciphertext = f.read()

            print("[DECRYPT] Encryption type:", encryption_type)
            print("[DECRYPT] Key (hex):", key.hex())
            print("[DECRYPT] IV (hex):", iv.hex() if iv else "None")
            print("[DECRYPT] Ciphertext sample:", ciphertext[:20])

            # التحقق حسب نوع التشفير
            if encryption_type == "AES":
                if iv is None or len(iv) != 16:
                    raise ValueError("AES IV must be 16 bytes.")
                if len(ciphertext) % 16 != 0:
                    raise ValueError("AES ciphertext must be multiple of 16 bytes.")
                cipher = AES.new(key, AES.MODE_CBC, iv)
                padded_plaintext = cipher.decrypt(ciphertext)
                plaintext = padded_plaintext[:-padded_plaintext[-1]]

            elif encryption_type == "ChaCha20":
                if iv is None or len(iv) != 12:
                    raise ValueError("ChaCha20Poly1305 IV must be 12 bytes.")
                if len(ciphertext) < 16:
                    raise ValueError("ChaCha20 ciphertext too short.")
                try:
                    cipher = ChaCha20Poly1305(key)
                    plaintext = cipher.decrypt(iv, ciphertext, None)
                except Exception as e:
                    raise ValueError(f"ChaCha20 Decryption Failed: {str(e)}")

            elif encryption_type == "Blowfish":
                if iv is None or len(iv) != 8:
                    raise ValueError("Blowfish IV must be 8 bytes.")
                if len(ciphertext) % 8 != 0:
                    raise ValueError("Blowfish ciphertext must be multiple of 8 bytes.")
                cipher = Blowfish.new(key, Blowfish.MODE_CBC, iv)
                padded_plaintext = cipher.decrypt(ciphertext)
                plaintext = padded_plaintext[:-padded_plaintext[-1]]

            else:
                QMessageBox.critical(None, "خطأ", "نوع التشفير غير مدعوم.")
                return

            save_path, _ = QFileDialog.getSaveFileName(None, "Save Decrypted File", self.filename.replace("enc_", ""))
            if not save_path:
                return

            with open(save_path, 'wb') as f:
                f.write(plaintext)

            decrypted_name = os.path.basename(save_path)
            item = QListWidgetItem(f"{decrypted_name} (Decrypted)")
            self.decrypted_list.addItem(item)

            history_path = "decrypted_files.json"
            if os.path.exists(history_path):
                with open(history_path, "r") as f:
                    data = json.load(f)
            else:
                data = []

            if decrypted_name not in data:
                data.append(decrypted_name)

            with open(history_path, "w") as f:
                json.dump(data, f)

            QMessageBox.information(None, "تم", "تم فك التشفير بنجاح.")

        except self.s3_client.exceptions.NoSuchKey:
            QMessageBox.critical(None, "Error", f"The file '{s3_key}' was not found in the S3 bucket.")

        except Error as e:
            QMessageBox.critical(None, "Database Error", str(e))

        except Exception as e:
            # حفظ الملف الذي فشل لفحصه لاحقًا
            failed_dir = os.path.join(os.getcwd(), "failed_decrypts")
            os.makedirs(failed_dir, exist_ok=True)
            with open(os.path.join(failed_dir, safe_filename), 'wb') as f:
                f.write(ciphertext)

            QMessageBox.critical(None, "Error", f"حدث خطأ أثناء فك التشفير:\n{str(e)}")
            print(f"[DECRYPT] Error occurred for {self.filename}")
            print(f"[DECRYPT] Exception: {str(e)}")
            print(f"[DECRYPT] Downloaded ciphertext size: {len(ciphertext)} bytes")

# ======= دوال مساعدة =======

def is_video_file(filename):
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
    filename = filename.strip().lower()
    return any(filename.endswith(ext) for ext in video_extensions)

def is_image_file(filename):
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']
    filename = filename.strip().lower()
    return any(filename.endswith(ext) for ext in image_extensions)

def is_document_file(filename):
    document_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt']
    filename = filename.strip().lower()
    return any(filename.endswith(ext) for ext in document_extensions)

def normalize_filename(filename):
    filename = filename.strip().replace(' ', '_')
    filename = re.sub(r'[^A-Za-z0-9_.-]', '', filename)
    return filename
