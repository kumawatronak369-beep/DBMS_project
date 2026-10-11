from db import get_connection


connection = get_connection()

if connection:
    print("MySQL connection successful!")

    cursor = connection.cursor()

    cursor.execute("SELECT DATABASE(), VERSION();")

    result = cursor.fetchone()

    print("Database:", result[0])
    print("MySQL version:", result[1])

    cursor.close()
    connection.close()

else:
    print("MySQL connection failed.")