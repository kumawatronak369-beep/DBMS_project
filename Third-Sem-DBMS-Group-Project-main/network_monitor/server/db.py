import mysql.connector
from mysql.connector import Error


DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "database": "network_monitor",
    "user": "network_app",
    "password": "YOUR_NEW_PASSWORD"
}


def get_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)

        if connection.is_connected():
            return connection

    except Error as error:
        print(f"MySQL connection error: {error}")

    return None