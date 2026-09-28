# import html
# import re
# import socket
# import sys
# from urllib.parse import parse_qs, unquote_to_bytes, urlsplit
# HOST = "127.0.0.1"
# PORT = 8000
# REQUEST_TIMEOUT_SECONDS = 1.0
# MAX_HEADER_SIZE = 16 * 1024
# MAX_BODY_SIZE = 1024 * 1024
# messages = []
# PAGES = {
#     "/": "<h1>Homepage</h1>",
#     "/about": "<h1>О нас</h1><p>Это страница о нашей компании.</p>",
#     "/services": "<h1>Услуги</h1><p>Здесь перечислены наши услуги.</p>",
#     "/contact": "<h1>Контакты</h1><p>Email: example@mail.com</p>",
# }
# class BadRequest(Exception):
#     pass
# class PayloadTooLarge(Exception):
#     pass
# def bad_request_page():
#     return "400 Bad Request", "<h1>400 — Некорректный запрос</h1>"
# def forbidden_page():
#     return "403 Forbidden", "<h1>403 — Доступ запрещён</h1>"
# def not_found_page():
#     return "404 Not Found", "<h1>404 — Страница не найдена</h1>"
# def method_not_allowed_page():
#     return "405 Method Not Allowed", "<h1>405 — Метод не поддерживается</h1>"
# def payload_too_large_page():
#     return "413 Payload Too Large", "<h1>413 — Слишком большой запрос</h1>"
# def static_page(path, _body):
#     return "200 OK", PAGES[path]
# def admin_page(_path, _body):
#     return forbidden_page()
# def hello_form_page(_path, _body):
#     body = """
#     <h1>Приветствуем</h1>
#     <p>Как вас зовут?</p>
#     <form action="/hello" method="get">
#         <label for="name">Ваше имя:</label>
#         <input id="name" name="name" required autofocus>
#         <button type="submit">Enter</button>
#     </form>
#     """
#     return "200 OK", body
# def hello_page(path, _body):
#     name = html.escape(path.removeprefix("/hello/"))
#     return "200 OK", f"<h1>Привет, {name}!</h1>"
# def get_messages(_path, _body):
#     if not messages:
#         body = "<h1>Сообщения</h1><p>Сообщений пока нет.</p>"
#     else:
#         items = "".join(f"<li>{html.escape(message)}</li>" for message in messages)
#         body = f"<h1>Сообщения</h1><ul>{items}</ul>"
#     return "200 OK", body
# def post_messages(_path, body):
#     messages.append(body.decode("utf-8", errors="replace"))
#     return "201 Created", "<h1>201 — Сообщение сохранено</h1>"
# ROUTES = {
#     **{path: {"GET": static_page} for path in PAGES},
#     "/admin": {"GET": admin_page},
#     "/hello": {"GET": hello_form_page},
#     "/messages": {"GET": get_messages, "POST": post_messages},
# }
# def find_route(method, path):
#     if path.startswith("/hello/") and len(path) > len("/hello/"):
#         handlers = {"GET": hello_page}
#     else:
#         handlers = ROUTES.get(path)
#     if handlers is None:
#         return None, None
#     return handlers.get(method), tuple(handlers)
# def create_response(status, body, headers=None):
#     body_bytes = body.encode("utf-8")
#     response_headers = {
#         "Content-Type": "text/html; charset=utf-8",
#         "Content-Length": str(len(body_bytes)),
#         "Connection": "close",
#     }
#     if headers:
#         response_headers.update(headers)
#     header_lines = "".join(
#         f"{name}: {value}\r\n"
#         for name, value in response_headers.items()
#     )
#     return (
#         f"HTTP/1.1 {status}\r\n{header_lines}\r\n".encode("utf-8")
#         + body_bytes
#     )
# def decode_path(request_target):
#     parsed = urlsplit(request_target)
#     if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
#         raise BadRequest
#     if re.search(r"%(?![0-9A-Fa-f]{2})", parsed.path):
#         raise BadRequest
#     path_bytes = unquote_to_bytes(parsed.path)
#     try:
#         path = path_bytes.decode("utf-8") or "/"
#     except UnicodeDecodeError:
#         path = path_bytes.decode("cp1251", errors="replace") or "/"
#     if path == "/hello":
#         name = parse_qs(parsed.query, keep_blank_values=True).get("name", [None])[0]
#         if name:
#             return f"/hello/{name}"
#     return path
# def parse_headers(header_bytes):
#     try:
#         lines = header_bytes.decode("utf-8").split("\r\n")
#         method, target, protocol = lines[0].split()
#     except (UnicodeDecodeError, IndexError, ValueError) as error:
#         raise BadRequest from error
#     if not protocol.startswith("HTTP/"):
#         raise BadRequest
#     headers = {}
#     for line in lines[1:]:
#         if not line or ":" not in line:
#             raise BadRequest
#         name, value = line.split(":", 1)
#         name = name.strip().lower()
#         if not name or name in headers:
#             raise BadRequest
#         headers[name] = value.strip()
#     return method.upper(), decode_path(target), headers
# def read_headers(conn):
#     data = bytearray()
#     while True:
#         try:
#             chunk = conn.recv(4096)
#         except socket.timeout as error:
#             raise BadRequest from error
#         if not chunk:
#             raise BadRequest
#         data.extend(chunk)
#         end_of_headers = data.find(b"\r\n\r\n")
#         if end_of_headers != -1:
#             if end_of_headers > MAX_HEADER_SIZE:
#                 raise PayloadTooLarge
#             break
#         if len(data) > MAX_HEADER_SIZE:
#             raise PayloadTooLarge
#     header_bytes, _, initial_body = bytes(data).partition(b"\r\n\r\n")
#     return header_bytes, initial_body
# def get_content_length(headers):
#     value = headers.get("content-length", "0")
#     if not re.fullmatch(r"[0-9]+", value):
#         raise BadRequest
#     content_length = int(value)
#     if content_length > MAX_BODY_SIZE:
#         raise PayloadTooLarge
#     return content_length
# def read_body(conn, initial_body, content_length):
#     body = bytearray(initial_body[:content_length])
#     while len(body) < content_length:
#         try:
#             chunk = conn.recv(min(4096, content_length - len(body)))
#         except socket.timeout as error:
#             raise BadRequest from error
#         if not chunk:
#             raise BadRequest
#         body.extend(chunk)
#     return bytes(body)
# def handle_request(conn):
#     try:
#         header_bytes, initial_body = read_headers(conn)
#         method, path, headers = parse_headers(header_bytes)
#         handler, allowed_methods = find_route(method, path)
#         if allowed_methods is None:
#             status, body = not_found_page()
#             return create_response(status, body)
#         if handler is None:
#             status, body = method_not_allowed_page()
#             return create_response(
#                 status,
#                 body,
#                 {"Allow": ", ".join(allowed_methods)},
#             )
#         body_bytes = b""
#         if method == "POST":
#             body_bytes = read_body(
#                 conn,
#                 initial_body,
#                 get_content_length(headers),
#             )
#         status, body = handler(path, body_bytes)
#         return create_response(status, body)
#     except PayloadTooLarge:
#         status, body = payload_too_large_page()
#         return create_response(status, body)
#     except BadRequest:
#         status, body = bad_request_page()
#         return create_response(status, body)
# def run_server(host=HOST, port=PORT):
#     with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
#         server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#         server.bind((host, port))
#         server.listen(5)
#         print(f"Сервер запущен: http://{host}:{port}")
#         while True:
#             conn, _address = server.accept()
#             with conn:
#                 conn.settimeout(REQUEST_TIMEOUT_SECONDS)
#                 conn.sendall(handle_request(conn))
# if __name__ == "__main__":
#     selected_port = int(sys.argv[1]) if len(sys.argv) == 2 else PORT
#     run_server(port=selected_port)
from dns.message import MessageSection
# import http
# import socket
# from urllib.parse import urlsplit, parse_qs
# def home():
#     return "<h1>Homepage</h1>"
# def about():
#     return "<h1>О нас</h1><p>Это страница о нашей компании.</p>"
# def services():
#     return "<h1>Услуги</h1><p>Здесь перечислены наши услуги.</p>"
# def contacts():
#     return "<h1>Контакты</h1><p>Email: example@mail.com</p>"
# def help():
#     return "<h1>Помощь</h1><p>Если у вас есть вопросы, обратитесь к нам.</p>"
# def hello():
#     return "<h1>Hello!</h1><p>Как вас зовут?</p>"
# pages = {
#     "/about": about,
#     "/services": services,
#     "/contacts": contacts,
#     "/help": help,
# }
# def create_response(status, body):
#     body_bytes = body.encode("utf-8")
#     response = (
#         f"HTTP/1.1 {status}\r\n"
#         "Content-Type: text/html; charset=utf-8\r\n"
#         f"Content-Length: {len(body_bytes)}\r\n"
#         "Connection: close\r\n"
#         "\r\n"
#     ).encode("utf-8") + body_bytes
#     return response
# def handle_request(req):
#     try:
#         request_lines = req.decode("utf-8").splitlines()
#         print("\nПолучен запрос:")
#         print(request_lines)
#         if not request_lines:
#             return create_response(
#                 "400 Bad Request",
#                 "<h1>400 — Пустой запрос</h1>"
#             )
#         method, path, proto = request_lines[0].split()
#         print("Метод:", method)
#         print("Путь:", path)
#         print("Протокол:", proto)
#         if method != "GET":
#             return create_response(
#                 "405 Method Not Allowed",
#                 "<h1>405 — Метод не поддерживается</h1>"
#             )
#         url = urlsplit(path)
#         route = url.path
#         query = parse_qs(url.query)
#         print("Route:", route)
#         print("Query:", query)
#         if route == "/":
#             route = "/hello"
#         if route == "/hello":
#             name = query.get("name", [""])[0]
#             if name:
#                 body = f"""
#                 <!DOCTYPE html>
#                 <html lang="ru">
#                 <head>
#                     <meta charset="UTF-8">
#                     <title>Hello, {name}!</title>
#                 </head>
#                 <body>
#                     <h1>Hello, {name}!</h1>
#                     <p>
#                         Рады вас видеть.
#                     </p>
#                     <hr>
#                     <h2>Изменить имя</h2>
#                     <form action="/hello" method="GET">
#                         <input
#                             type="text"
#                             name="name"
#                             value="{name}"
#                             required
#                         >
#                         <button type="submit">
#                             Изменить
#                         </button>
#                     </form>
#                     <br>
#                     <a href="/">
#                         Вернуться на главную
#                     </a>
#                     <hr>
#                     <h2>Другие страницы</h2>
#                     <a href="/about">
#                         О нас
#                     </a>
#                     <br>
#                     <a href="/services">
#                         Услуги
#                     </a>
#                     <br>
#                     <a href="/contacts">
#                         Контакты
#                     </a>
#                     <br>
#                     <a href="/help">
#                         Помощь
#                     </a>
#                 </body>
#                 </html>
#                 """
#                 return create_response(
#                     "200 OK",
#                     body
#                 )
#             body = """
#             <!DOCTYPE html>
#             <html lang="ru">
#             <head>
#                 <meta charset="UTF-8">
#                 <title>Hello</title>
#             </head>
#             <body>
#                 <h1>Hello!</h1>
#                 <p>
#                     Как вас зовут?
#                 </p>
#                 <form action="/hello" method="GET">
#                     <input
#                         type="text"
#                         name="name"
#                         placeholder="Введите имя"
#                         required
#                     >
#                     <button type="submit">
#                         Продолжить
#                     </button>
#                 </form>
#                 <hr>
#                 <h2>Другие страницы</h2>
#                 <a href="/about">
#                     О нас
#                 </a>
#                 <br>
#                 <a href="/services">
#                     Услуги
#                 </a>
#                 <br>
#                 <a href="/contacts">
#                     Контакты
#                 </a>
#                 <br>
#                 <a href="/help">
#                     Помощь
#                 </a>
#             </body>
#             </html>
#             """
#             return create_response(
#                 "200 OK",
#                 body
#             )
#         if route == "/admin":
#             body = """
#             <!DOCTYPE html>
#             <html lang="ru">
#             <head>
#                 <meta charset="UTF-8">
#                 <title>403</title>
#             </head>
#             <body>
#                 <h1>403 — Доступ запрещён</h1>
#             </body>
#             </html>
#             """
#             return create_response(
#                 "403 Forbidden",
#                 body
#             )
#         if route in pages:
#             body = f"""
#             <!DOCTYPE html>
#             <html lang="ru">
#             <head>
#                 <meta charset="UTF-8">
#                 <title>Страница</title>
#             </head>
#             <body>
#                 {pages[route]()}
#                 <br>
#                 <hr>
#                 <a href="/">
#                     На главную
#                 </a>
#             </body>
#             </html>
#             """
#             return create_response(
#                 "200 OK",
#                 body
#             )
#         body = """
#         <!DOCTYPE html>
#         <html lang="ru">
#         <head>
#             <meta charset="UTF-8">
#             <title>404</title>
#         </head>
#         <body>
#             <h1>404 — Страница не найдена</h1>
#             <p>
#                 Такой страницы не существует.
#             </p>
#             <a href="/">
#                 Вернуться на главную
#             </a>
#         </body>
#         </html>
#         """
#         return create_response(
#             "404 Not Found",
#             body
#         )
#     except UnicodeDecodeError:
#         return create_response(
#             "400 Bad Request",
#             "<h1>400 — Ошибка кодировки</h1>"
#         )
#     except (IndexError, ValueError):
#         return create_response(
#             "400 Bad Request",
#             "<h1>400 — Некорректный запрос</h1>"
#         )
#     except Exception as e:
#         print("Ошибка:", e)
#         return create_response(
#             "500 Internal Server Error",
#             "<h1>500 — Внутренняя ошибка сервера</h1>"
#         )
# def run_server():
#     server = socket.socket(
#         socket.AF_INET,
#         socket.SOCK_STREAM
#     )
#     server.setsockopt(
#         socket.SOL_SOCKET,
#         socket.SO_REUSEADDR,
#         1
#     )
#     server.bind(
#         ("127.0.0.1", 8000)
#     )
#     server.listen(5)
#     print(
#         "Сервер запущен:"
#         " http://127.0.0.1:8000"
#     )
#     while True:
#         conn, address = server.accept()
#         print(
#             "\nПодключение:",
#             address
#         )
#         conn.settimeout(5)
#         try:
#             req = conn.recv(4096)
#             if not req:
#                 conn.close()
#                 continue
#             response = handle_request(req)
#             conn.sendall(response)
#         except TimeoutError:
#             response = create_response(
#                 "400 Bad Request",
#                 """
#                 <h1>
#                     400 — Время ожидания запроса истекло
#                 </h1>
#                 """
#             )
#             conn.sendall(response)
#         except ConnectionError:
#             print(
#                 "Соединение было закрыто клиентом"
#             )
#         finally:
#             conn.close()
# if __name__ == "__main__":
#     run_server()

# from fastapi import FastAPI
# app = FastAPI()
# @app.get("/hello/{name}")
# def hello(name: str):
#     return {"message": name}

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
app = FastAPI()

class MessageIn(BaseModel):
    author: str
    text: str

class MessageOut(MessageIn):
    id: int

MESSAGES: list[MessageOut] = []
next_id = 1


@app.get("/messages", response_model=list[MessageOut])
def list_messages() -> list[MessageOut]:
    return MESSAGES


@app.post("/messages", response_model=MessageOut, status_code=201)
def create_message(payload: MessageIn) -> MessageOut:
    global next_id
    message = MessageOut(
        id=next_id,
        author=payload.author,
        text=payload.text,
    )
    MESSAGES.append(message)
    next_id += 1
    return message

def find(message_id: int) -> MessageOut:
    for message in MESSAGES:
        if message.id == message_id:
            return message
    raise HTTPException(status_code=404, detail="Message not found")
@app.delete("/messages/{message_id}", status_code=204)
def delete_message(message_id: int) -> None:
    MESSAGES.remove(find(message_id))