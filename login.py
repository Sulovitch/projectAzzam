import sys
import cv2
import mysql.connector
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QLineEdit, QPushButton,
                             QVBoxLayout, QHBoxLayout, QMessageBox, QFrame, QMainWindow)


from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from dashboard import Dashboard  # Import the Dashboard class from dashboard.py


# Database Setup
def init_db():
    conn = mysql.connector.connect(host="localhost", user="root", password="root",
                                   database="filestoragedb")
    cursor = conn.cursor()

    conn.commit()
    conn.close()


# Face Recognition Functions
def capture_face(username):
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(0)

    # Create window with instructions
    cv2.namedWindow("Capture Face", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Capture Face", 640, 480)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        # Draw rectangle and instructions
        cv2.putText(frame, "Position your face in the frame and press SPACE", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, "Press Q to cancel", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        for (x, y, w, h) in faces:
            # Draw rectangle around detected face
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

        cv2.imshow("Capture Face", frame)
        key = cv2.waitKey(1) & 0xFF

        # Space key to capture
        if key == 32 and len(faces) > 0:
            for (x, y, w, h) in faces:
                face = frame[y:y + h, x:x + w]

                # Convert the face image to binary data
                _, img_encoded = cv2.imencode('.jpg', face)
                img_binary = img_encoded.tobytes()

                # Save binary data in the database
                conn = mysql.connector.connect(host="localhost", user="root", password="root",
                                              database="filestoragedb")
                cursor = conn.cursor()
                cursor.execute("UPDATE user SET ProfileImage=%s WHERE UserName=%s", (img_binary, username))
                conn.commit()
                conn.close()

                cap.release()
                cv2.destroyAllWindows()
                return "Face captured and saved in the database."

        # Q key to quit
        elif key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    return None

def recognize_face():
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(0)

    # Create window with instructions
    cv2.namedWindow("Face Recognition", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Face Recognition", 640, 480)

    # Retrieve stored faces from the database
    conn = mysql.connector.connect(host="localhost", user="root", password="root",
                                   database="filestoragedb")
    cursor = conn.cursor()
    cursor.execute("SELECT UserName, ProfileImage FROM user WHERE ProfileImage IS NOT NULL")
    users = cursor.fetchall()
    conn.close()

    if not users:
        print("No users with face data found in the database.")
        cap.release()
        cv2.destroyAllWindows()
        return None

    attempts = 0
    max_attempts = 100  # About 5 seconds at 6 FPS

    while attempts < max_attempts:
        ret, frame = cap.read()
        if not ret:
            print("Failed to capture frame from camera.")
            break

        attempts += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        # Add instructions
        cv2.putText(frame, "Looking for your face...", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"Attempt {attempts}/{max_attempts}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        for (x, y, w, h) in faces:
            # Draw rectangle around detected face
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

            face = frame[y:y + h, x:x + w]
            temp_path = "temp_face.jpg"
            cv2.imwrite(temp_path, face)

            # Compare with stored faces
            for username, profile_image in users:
                if profile_image is not None:
                    # Save the binary data to a temporary file
                    with open("temp_stored_face.jpg", "wb") as file:
                        file.write(profile_image)
                    stored_face = cv2.imread("temp_stored_face.jpg")
                    if stored_face is not None:
                        # Resize both images to the same dimensions
                        stored_face_resized = cv2.resize(stored_face, (face.shape[1], face.shape[0]))

                        # Calculate the Mean Squared Error (MSE) between the two images
                        mse = ((stored_face_resized - face) ** 2).mean()

                        # If MSE is below a threshold, consider it a match
                        if mse < 5000:  # Adjust this threshold as needed
                            print(f"Face recognized for user: {username}")
                            cap.release()
                            cv2.destroyAllWindows()
                            os.remove(temp_path)
                            os.remove("temp_stored_face.jpg")
                            return username

        cv2.imshow("Face Recognition", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("Face recognition process cancelled by user.")
            break

    cap.release()
    cv2.destroyAllWindows()
    if os.path.exists("temp_face.jpg"):
        os.remove("temp_face.jpg")
    if os.path.exists("temp_stored_face.jpg"):
        os.remove("temp_stored_face.jpg")
    print("Face not recognized.")
    return None

# Styled Components
class StyledLineEdit(QLineEdit):
    def __init__(self, placeholder=""):
        super().__init__()
        self.setPlaceholderText(placeholder)
        self.setMinimumHeight(40)
        self.setStyleSheet("""
            QLineEdit {
                border: 2px solid #ccc;
                border-radius: 5px;
                padding: 5px 10px;
                background-color: #f8f8f8;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #4a90e2;
                background-color: white;
            }
        """)


class StyledButton(QPushButton):
    def __init__(self, text, primary=True):
        super().__init__(text)
        self.setMinimumHeight(40)
        if primary:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #4a90e2;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 8px 16px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #357ab7;
                }
                QPushButton:pressed {
                    background-color: #2a5885;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0;
                    color: #333;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    padding: 8px 16px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
                QPushButton:pressed {
                    background-color: #d0d0d0;
                }
            """)


# Main Login UI
class LoginApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Secure Login System")
        self.setGeometry(100, 100, 500, 600)
        self.setStyleSheet("background-color: #ecf0f1;")  # لون خلفية هادئ

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(40, 40, 40, 40)

        # App title
        title_label = QLabel("Secure Login")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            font-size: 28px;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 20px;
        """)
        main_layout.addWidget(title_label)

        # Login form
        form_frame = QFrame()
        form_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 15px;
                border: 1px solid #bdc3c7;
                padding: 20px;
                box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.1);
            }
        """)
        form_layout = QVBoxLayout(form_frame)
        form_layout.setSpacing(15)

        # Username field
        username_label = QLabel("Username")
        username_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #34495e;
        """)
        self.username_input = StyledLineEdit("Enter your username")
        form_layout.addWidget(username_label)
        form_layout.addWidget(self.username_input)

        # Password field
        password_label = QLabel("Password")
        password_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #34495e;
        """)
        self.password_input = StyledLineEdit("Enter your password")
        self.password_input.setEchoMode(QLineEdit.Password)
        form_layout.addWidget(password_label)
        form_layout.addWidget(self.password_input)

        # Login button
        self.login_button = StyledButton("Login")
        self.login_button.clicked.connect(self.login)
        form_layout.addWidget(self.login_button)

        # Register button
        self.register_button = StyledButton("Register", False)
        self.register_button.clicked.connect(self.register)
        form_layout.addWidget(self.register_button)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        divider.setStyleSheet("background-color: #ddd;")
        form_layout.addWidget(divider)

        # Face login button
        face_login_layout = QHBoxLayout()
        face_login_label = QLabel("Or login with:")
        face_login_label.setStyleSheet("font-size: 14px; color: #34495e;")
        face_login_layout.addWidget(face_login_label)

        self.face_login_button = StyledButton("Face Recognition", False)
        self.face_login_button.setStyleSheet("""
            QPushButton {
                background-color: #4267B2;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #365899;
            }
        """)
        self.face_login_button.clicked.connect(self.face_login)
        face_login_layout.addWidget(self.face_login_button)

        form_layout.addLayout(face_login_layout)

        main_layout.addWidget(form_frame)

        # Status messages
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("""
            color: #e74c3c;
            font-size: 14px;
            min-height: 20px;
        """)
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)

    def open_dashboard(self, username,user_id):
        self.dashboard = Dashboard(username, user_id)
        self.dashboard.show()
        self.close()

    def login(self):
        username = self.username_input.text()
        password = self.password_input.text()

        if not username or not password:
            self.status_label.setText("Please enter both username and password")
            return

        try:
            conn = mysql.connector.connect(host="localhost", user="root", password="root",
                                           database="filestoragedb")
            cursor = conn.cursor()

            cursor.execute("SELECT  Password, UserID FROM user WHERE UserName=%s", (username,))
            user = cursor.fetchone()
            conn.close()

            if user and user[0] == password:
                self.status_label.setText("")
                user_id = user[1]
                self.open_dashboard(username, user_id)
            else:
                self.status_label.setText("Invalid username or password")
        except mysql.connector.Error as err:
            self.status_label.setText(f"Database error: {err}")



    def register(self):
        username = self.username_input.text()
        password = self.password_input.text()

        if not username or not password:
            self.status_label.setText("Please enter both username and password")
            return

        try:
            conn = mysql.connector.connect(
                host="localhost",
                user="root",
                password="root",
                database="filestoragedb"
            )
            cursor = conn.cursor()

            # 🔍 تحقق إذا اليوزر موجود مسبقاً
            cursor.execute("SELECT * FROM user WHERE UserName = %s", (username,))
            existing_user = cursor.fetchone()

            if existing_user:
                self.status_label.setText("Username already exists, please choose another")
                return

            # ✅ إضافة المستخدم الجديد
            cursor.execute(
                "INSERT INTO user (UserName, Password) VALUES (%s, %s)",
                (username, password)
            )
            conn.commit()

            # 💬 رسالة بعد التسجيل
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Face Recognition")
            msg_box.setText("Registration successful! Would you like to add face recognition for quicker login?")
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            response = msg_box.exec_()

            if response == QMessageBox.Yes:
                face_path = capture_face(username)
                if face_path:
                    self.status_label.setText("Registration with face complete!")
                else:
                    self.status_label.setText("Registration successful, but face capture was cancelled")
            else:
                self.status_label.setText("Registration successful!")

        except mysql.connector.Error as err:
            self.status_label.setText(f"Registration error: {err}")

        finally:
            conn.close()


    def face_login(self):
        recognized_user = recognize_face()

        if recognized_user:
            try:
                conn = mysql.connector.connect(
                    host="localhost", user="root", password="root", database="filestoragedb"
                )
                cursor = conn.cursor()

                # جلب user_id بناءً على اسم المستخدم المعروف
                cursor.execute("SELECT UserID FROM user WHERE UserName = %s", (recognized_user,))
                result = cursor.fetchone()

                if result:
                    user_id = result[0]
                    self.open_dashboard(recognized_user, user_id)
                else:
                    self.status_label.setText("User not found in the database")

            except mysql.connector.Error as err:
                self.status_label.setText(f"Database error: {err}")
            finally:
                conn.close()
        else:
            self.status_label.setText("Face not recognized")



# Main execution
if __name__ == "__main__":
    try:
        init_db()
        app = QApplication(sys.argv)
        app.setStyle('Fusion')  # Use Fusion style for a modern look
        window = LoginApp()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Error starting application: {e}")



