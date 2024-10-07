import socket
import threading
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import urllib.parse
import os
import pymongo
from pymongo.errors import ServerSelectionTimeoutError

# Конфігурація для MongoDB
mongo_uri = os.getenv("MONGO_URI", "mongodb://mongodb_service:27017")
client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)

# Перевірка доступу до MongoDB
try:
    client.admin.command('ping')
    print("Підключено до MongoDB")
except ServerSelectionTimeoutError:
    print("MongoDB недоступна")

# Вибір бази даних і колекції
db = client.messages_db
collection = db.messages


# Обробник для HTTP-запитів
class HttpGetHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_html_file('index.html')
        elif self.path == '/message.html':
            self.send_html_file('message.html')
        elif self.path == '/style.css':
            self.send_static('style.css', 'text/css')
        elif self.path == '/logo.png':
            self.send_static('logo.png', 'image/png')
        else:
            self.send_html_file('error.html', 404)

    def do_POST(self):
        if self.path == '/message':
            # Обробка форми
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(body.decode('utf-8'))

            # Витягуємо дані з форми
            username = data.get("username", [""])[0]
            message = data.get("message", [""])[0]
            
            # Лог повідомлення
            print(f"Отримано повідомлення: {username}, {message}")

            if username and message:
                # Надсилаємо повідомлення на Socket-сервер
                send_data_to_socket(username, message)

                # Перенаправляємо на головну сторінку
                self.send_response(302)
                self.send_header('Location', '/')
                self.end_headers()
            else:
                # Помилка якщо форма порожня
                self.send_html_file('error.html', 400)

    def send_html_file(self, filename, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        with open(filename, 'rb') as file:
            self.wfile.write(file.read())

    def send_static(self, filename, content_type):
        self.send_response(200)
        self.send_header('Content-type', content_type)
        self.end_headers()
        with open(filename, 'rb') as file:
            self.wfile.write(file.read())


# Відправка даних на сокет-сервер
def send_data_to_socket(username, message):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address = ('localhost', 5000)
    message_data = {
        "username": username,
        "message": message
    }
    # Відправляємо дані
    sock.sendto(json.dumps(message_data).encode('utf-8'), server_address)
    print(f"Відправлено на сокет-сервер: {message_data}")


# Функція для збереження даних у MongoDB
def save_data(data):
    try:
        # Збереження в MongoDB
        message_data = json.loads(data)
        message_data['date'] = str(datetime.now())
        collection.insert_one(message_data)
        print(f"Повідомлення збережено в MongoDB: {message_data}")
    except Exception as e:
        print(f"Помилка збереження даних у MongoDB: {e}")


# Сокет-сервер для прийому повідомлень
def run_socket_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address = ('localhost', 5000)
    sock.bind(server_address)
    print("Socket сервер працює на порту 5000")

    while True:
        data, _ = sock.recvfrom(1024)
        print(f"Отримано дані на сокет-сервері: {data}")
        save_data(data)


# Запуск HTTP-сервера
def run_http_server():
    server_address = ('0.0.0.0', 3000)
    httpd = HTTPServer(server_address, HttpGetHandler)
    print("HTTP сервер працює на порту 3000")
    httpd.serve_forever()


if __name__ == '__main__':
    # Запускаємо HTTP та сокет-сервери
    threading.Thread(target=run_http_server).start()
    threading.Thread(target=run_socket_server).start()
