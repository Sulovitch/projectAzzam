import os
import boto3
import datetime
import cv2
from Crypto.Cipher import AES, Blowfish
from Crypto.Random import get_random_bytes
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from mysql.connector import Error
from PIL import Image, ExifTags
import json  # لإضافة سجل logging

class EncryptHelper:

    @staticmethod
    def get_file_type_from_extension(ext):
        ext = ext.lower()

        image_exts = [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif", ".webp", ".ico", ".heic"]
        video_exts = [".mp4", ".avi", ".mov", ".wmv", ".mkv", ".flv", ".webm", ".3gp", ".mpeg", ".mpg"]
        file_exts = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".zip", ".rar", ".7z", ".tar", ".gz", ".json", ".xml"]

        if ext in image_exts:
            return "image"
        elif ext in video_exts:
            return "video"
        elif ext in file_exts:
            return "file"
        else:
            return "file"

    @staticmethod
    def pad_data(data, block_size):
        pad_len = block_size - len(data) % block_size
        return data + bytes([pad_len] * pad_len)

    @staticmethod
    def extract_capture_datetime(file_path):
        try:
            image = Image.open(file_path)
            exif_data = image._getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag = ExifTags.TAGS.get(tag_id, tag_id)
                    if tag == 'DateTimeOriginal':
                        return datetime.datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
        except Exception:
            pass
        return None

    @staticmethod
    def get_video_duration(file_path):
        try:
            cap = cv2.VideoCapture(file_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()
            if fps > 0:
                total_seconds = int(frame_count / fps)
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except Exception:
            pass
        return None

    @staticmethod
    def encrypt_file(file_path, encryption_type, username, user_id, s3_client, s3_bucket, db_connection):
        with open(file_path, 'rb') as f:
            plaintext = f.read()

        file_name = os.path.basename(file_path)
        file_ext = os.path.splitext(file_name)[1].lower()

        if encryption_type == "AES":
            key = get_random_bytes(16)
            iv = get_random_bytes(16)
            cipher = AES.new(key, AES.MODE_CBC, iv)
            padded = EncryptHelper.pad_data(plaintext, 16)
            ciphertext = cipher.encrypt(padded)

        elif encryption_type == "ChaCha20":
            key = ChaCha20Poly1305.generate_key()
            iv = get_random_bytes(12)
            cipher = ChaCha20Poly1305(key)
            ciphertext = cipher.encrypt(iv, plaintext, None)

        elif encryption_type == "Blowfish":
            key = get_random_bytes(16)
            iv = get_random_bytes(8)
            cipher = Blowfish.new(key, Blowfish.MODE_CBC, iv)
            padded = EncryptHelper.pad_data(plaintext, 8)
            ciphertext = cipher.encrypt(padded)

        else:
            raise ValueError("Unsupported encryption type")

        encrypted_filename = f"enc_{file_name}"
        encrypted_path = os.path.join("temp", encrypted_filename)
        os.makedirs("temp", exist_ok=True)

        with open(encrypted_path, 'wb') as f:
            f.write(ciphertext)

        # ✅ تحقق من كتابة الملف بشكل صحيح
        actual_size = os.path.getsize(encrypted_path)
        if actual_size != len(ciphertext):
            raise ValueError(f"File size mismatch: expected {len(ciphertext)}, got {actual_size}")

        # ✅ ارفع الملف
        s3_key = f"user_{user_id}/{encrypted_filename}"
        s3_client.upload_file(encrypted_path, s3_bucket, s3_key)

        file_type = EncryptHelper.get_file_type_from_extension(file_ext)
        upload_date = datetime.datetime.now()

        capture_datetime = EncryptHelper.extract_capture_datetime(file_path) if file_type == "image" else None
        video_duration = EncryptHelper.get_video_duration(file_path) if file_type == "video" else None
        video_size = os.path.getsize(file_path) if file_type == "video" else None

        try:
            cursor = db_connection.cursor()

            # ✅ تأكد أن الملف لم يتم رفعه سابقًا
            check_query = f"SELECT COUNT(*) FROM {file_type} WHERE OriginalName = %s AND UserID = %s"
            cursor.execute(check_query, (file_name, user_id))
            if cursor.fetchone()[0] > 0:
                raise Exception(f"This file '{file_name}' has already been encrypted and uploaded.")

            cursor.execute(
                "INSERT INTO encryptionmethod (EncryptionType, EncryptionKey, IV) VALUES (%s, %s, %s)",
                (encryption_type, key.hex(), iv.hex())
            )
            encryption_id = cursor.lastrowid

            if file_type == "image":
                cursor.execute(
                    "INSERT INTO image (UserID, ImageName, EncryptionID, OriginalName, UploadDate, CaptureDateTime) VALUES (%s, %s, %s, %s, %s, %s)",
                    (user_id, encrypted_filename, encryption_id, file_name, upload_date, capture_datetime)
                )
            elif file_type == "video":
                cursor.execute(
                    "INSERT INTO video (UserID, VideoName, EncryptionID, OriginalName, UploadDate, Duration, VideoSize) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (user_id, encrypted_filename, encryption_id, file_name, upload_date, video_duration, video_size)
                )
            else:
                cursor.execute(
                    "INSERT INTO file (UserID, FileName, EncryptionID, OriginalName, UploadDate) VALUES (%s, %s, %s, %s, %s)",
                    (user_id, encrypted_filename, encryption_id, file_name, upload_date)
                )

            db_connection.commit()
            cursor.close()

            # ✅ تسجيل سجل العملية
            log_data = {
                "File": file_name,
                "EncryptedFile": encrypted_filename,
                "Encryption": encryption_type,
                "Key": key.hex(),
                "IV": iv.hex(),
                "EncryptedSize": len(ciphertext),
                "S3Key": s3_key,
                "Date": upload_date.strftime('%Y-%m-%d %H:%M:%S')
            }
            with open("encryption_log.json", "a") as logf:
                logf.write(json.dumps(log_data) + "\n")

        except Error as e:
            raise Exception(f"Database error: {str(e)}")
        finally:
            if os.path.exists(encrypted_path):
                os.remove(encrypted_path)

        print(f"[ENCRYPT ✅] {file_name} encrypted and uploaded as {encrypted_filename}")
