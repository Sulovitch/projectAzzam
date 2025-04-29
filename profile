import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QMessageBox, QDateEdit
from PyQt5.QtCore import QDate, Qt, right
import mysql.connector

from login import LoginApp
from login import capture_face
from login import Dashboard

class DatabaseApp(QWidget):

    def __init__(self, username, user_id):
        super().__init__()
        self.username = username # Store username
        self.user_id = user_id
        self.dashboard = Dashboard(username, user_id)
        self.capture_face= capture_face
        self.initUI()
        self.initDB()

    def initUI(self):
        # Set up the UI
        self.setWindowTitle('Insert Data into MySQL DB')
        self.setGeometry(100, 100, 400, 300)

        # Create input fields
        self.phone_label = QLabel('Phone Number:', self)
        self.phone_input = QLineEdit(self)

        self.city_label = QLabel('City:', self)
        self.city_input = QLineEdit(self)

        self.birthday_label = QLabel('Birthday:', self)
        self.birthday_input = QDateEdit(self)
        self.birthday_input.setDisplayFormat("yyyy-MM-dd")
        self.birthday_input.setDate(QDate.currentDate())

        # Create a button to insert data
        self.insert_button = QPushButton('Register', self)
        self.insert_button.clicked.connect(self.insert_data)

        self.back = QPushButton('Back', self)
        self.back.clicked.connect(lambda: self.open_dashboard(self.username, self.user_id))

        self.face_login_button = QPushButton('Face Login', self)
        self.face_login_button.setStyleSheet("""
            QPushButton {
                background-color: #4267B2;  /* Facebook blue */
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #365899;  /* Darker blue on hover */
            }
            QPushButton:pressed {
                background-color: #2d4373;  /* Even darker when clicked */
            }
        """)
        self.face_login_button.clicked.connect(lambda: self.capture_face(self.username))
        # Set up the layout
        layout = QVBoxLayout()
        layout.addWidget(self.phone_label)
        layout.addWidget(self.phone_input)
        layout.addWidget(self.city_label)
        layout.addWidget(self.city_input)
        layout.addWidget(self.birthday_label)
        layout.addWidget(self.birthday_input)
        layout.addWidget(self.insert_button)


        layout.addWidget(self.face_login_button)

        self.setLayout(layout)

    def initDB(self):
        # Connect to MySQL database
        try:
            self.conn = mysql.connector.connect(
                host="localhost",
                user="root",
                password="root",
                database="filestoragedb"
            )
            self.cursor = self.conn.cursor()



            self.conn.commit()
        except mysql.connector.Error as e:
            QMessageBox.critical(self, 'Database Error', f'Failed to connect to MySQL: {e}')

    def insert_data(self,username):
        # Get data from input fields

        phone = self.phone_input.text()
        city = self.city_input.text()
        birthday = self.birthday_input.date().toString("yyyy-MM-dd")

        # Insert data into the database
        try:
            self.cursor.execute('''
               UPDATE user 
    SET PhoneNum = %s, City = %s, Birthday = %s 
    WHERE UserID = %s
            ''', ( phone, city, birthday,self.user_id)) #UPDATE user SET ProfileImage=%s WHERE UserName=%s
            self.conn.commit()
            #   INSERT INTO user (PhoneNum, City, Birthday)
            #                 VALUES (%s, %s, %s)
            # Show a success message
            QMessageBox.information(self, 'Success', 'Data inserted successfully!')

            # Clear input fields
            self.phone_input.clear()
            self.city_input.clear()
            self.birthday_input.setDate(QDate.currentDate())

        except mysql.connector.Error as e:
            # Show an error message if something goes wrong
            QMessageBox.critical(self, 'Error', f'An error occurred: {e}')

    def closeEvent(self, event):
        # Close the database connection when the application is closed
        if hasattr(self, 'conn') and self.conn.is_connected():
            self.cursor.close()
            self.conn.close()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = DatabaseApp()
    ex.show()
    sys.exit(app.exec_())
