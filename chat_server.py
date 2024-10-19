import socket
import threading
import mysql.connector
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ChatServer:
    def __init__(self, host='0.0.0.0', port=5555):
        self.host = host
        self.port = port
        self.clients = {}  # Store clients: {username: socket}
        self.rooms = {}  # Store chat rooms: {room_name: [usernames]}
        self.banned_users = set()

        # File sharing directory
        self.file_dir = "./shared_files/"
        os.makedirs(self.file_dir, exist_ok=True)

        # Connect to MySQL database
        try:
            self.db = mysql.connector.connect(
                host='localhost',
                user='root',
                password='admin',  
                database='chat_app'
            )
            logging.info("Successfully connected to the database")
        except mysql.connector.Error as err:
            logging.error(f"Error connecting to MySQL database: {err}")
            raise

        # Create server socket
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Prevent socket binding issues
            logging.info("Server socket created successfully")
        except socket.error as e:
            logging.error(f"Socket creation error: {e}")
            raise

    def start(self):
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            logging.info(f"Server is listening on {self.host}:{self.port}")
        except socket.error as e:
            logging.error(f"Socket binding error: {e}")
            raise

        while True:
            try:
                client_socket, address = self.server_socket.accept()
                logging.info(f"New connection from {address}")
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
                client_thread.start()
            except Exception as e:
                logging.error(f"Error accepting client connection: {e}")

    def handle_client(self, client_socket):
        username = None
        try:
            username = self.authenticate(client_socket)
            if not username:
                logging.info(f"Authentication failed for a client")
                return

            logging.info(f"User {username} authenticated successfully")
            self.clients[username] = client_socket
            self.broadcast(f"{username} has joined the chat!", None)

            while True:
                try:
                    message = client_socket.recv(1024).decode('utf-8')
                    if message:
                        logging.info(f"Received message from {username}: {message}")
                        if message.startswith('/'):
                            self.handle_command(message, username, client_socket)
                        else:
                            formatted_message = self.apply_formatting(message)
                            self.broadcast(f"{username}: {formatted_message}", username)
                    else:
                        logging.info(f"Empty message received from {username}, closing connection")
                        break
                except Exception as e:
                    logging.error(f"Error processing message from {username}: {str(e)}")
                    break
        except socket.error as e:
            logging.error(f"Socket error with client {username}: {str(e)}")
        except Exception as e:
            logging.error(f"Unexpected error with client {username}: {str(e)}", exc_info=True)
        finally:
            self.remove_client(username)

    def authenticate(self, client_socket):
        try:
            client_socket.send("Do you want to login, register, or admin? (login/register/admin): ".encode('utf-8'))
            choice = client_socket.recv(1024).decode('utf-8').strip().lower()
            logging.info(f"Authentication choice: {choice}")

            cursor = self.db.cursor()

            if choice == 'register':
                return self.register_user(client_socket, cursor)

            elif choice == 'login':
                return self.handle_login(client_socket, cursor)

            elif choice == 'admin':
                return self.handle_admin_login(client_socket, cursor)

            else:
                logging.warning(f"Invalid authentication choice: {choice}")
                client_socket.send("Invalid choice. Connection closed.".encode('utf-8'))
                return None
        except Exception as e:
            logging.error(f"Error during authentication: {e}")
            return None

    def register_user(self, client_socket, cursor):
        try:
            client_socket.send("Enter username: ".encode('utf-8'))
            username = client_socket.recv(1024).decode('utf-8').strip()

            client_socket.send("Enter password: ".encode('utf-8'))
            password = client_socket.recv(1024).decode('utf-8').strip()

            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
            self.db.commit()
            logging.info(f"New user registered: {username}")
            return username
        except mysql.connector.Error as err:
            logging.error(f"Database error during registration: {err}")
            client_socket.send("Registration failed. Please try again.".encode('utf-8'))
            return None

    def handle_login(self, client_socket, cursor):
        try:
            client_socket.send("Enter username: ".encode('utf-8'))
            username = client_socket.recv(1024).decode('utf-8').strip()

            client_socket.send("Enter password: ".encode('utf-8'))
            password = client_socket.recv(1024).decode('utf-8').strip()

            cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
            user = cursor.fetchone()

            if user:
                if username in self.banned_users:
                    client_socket.send("You are banned from this server.".encode('utf-8'))
                    logging.info(f"Banned user {username} attempted to log in")
                    return None
                logging.info(f"User {username} authenticated successfully")
                client_socket.send("Login successful".encode('utf-8'))
                return username
            else:
                client_socket.send("Invalid credentials. Try again.".encode('utf-8'))
                logging.info(f"Invalid credentials for user {username}")
                return None
        except mysql.connector.Error as err:
            logging.error(f"Database error during login: {err}")
            client_socket.send("Login failed. Please try again.".encode('utf-8'))
            return None

    def handle_admin_login(self, client_socket, cursor):
        try:
            client_socket.send("Enter admin username: ".encode('utf-8'))
            username = client_socket.recv(1024).decode('utf-8').strip()

            client_socket.send("Enter admin password: ".encode('utf-8'))
            password = client_socket.recv(1024).decode('utf-8').strip()

            cursor.execute("SELECT * FROM admins WHERE username=%s AND password=%s", (username, password))
            admin = cursor.fetchone()

            if admin:
                logging.info(f"Admin {username} authenticated successfully")
                client_socket.send("Admin login successful ".encode('utf-8'))
                return username
            else:
                client_socket.send("Invalid admin credentials. Try again.".encode('utf-8'))
                logging.info(f"Invalid admin credentials for {username}")
                return None
        except mysql.connector.Error as err:
            logging.error(f"Database error during admin login: {err}")
            client_socket.send("Admin login failed. Please try again.".encode('utf-8'))
            return None

    def handle_command(self, message, username, client_socket):
        parts = message.split()
        command = parts[0]

        if command == "/msg":
            if len(parts) < 3:
                client_socket.send("Usage: /msg <recipient> <message>".encode('utf-8'))
                return
            recipient = parts[1]
            msg = " ".join(parts[2:])
            self.private_message(username, recipient, msg)

        elif command == "/list_users":
            self.list_users(client_socket)

        elif command == "/delete_room":
            if len(parts) < 2:
                client_socket.send("Usage: /delete_room <room_name>".encode('utf-8'))
                return
            room_name = parts[1]
            self.delete_room(room_name, client_socket)

        elif command == "/create_room":
            if len(parts) < 2:
                client_socket.send("Usage: /create_room <room_name>".encode('utf-8'))
                return
            room_name = parts[1]
            self.create_room(username, room_name)

        elif command == "/list_rooms":
            self.list_rooms(client_socket)

        else:
            client_socket.send("Unknown command.".encode('utf-8'))

    def list_users(self, client_socket):
        """Send the list of online users to the requesting client."""
        user_list = ", ".join(self.clients.keys())
        client_socket.send(f"Online users: {user_list}".encode('utf-8'))
        logging.info(f"Sent user list to client")

    def delete_room(self, room_name, client_socket):
        """Delete a room if it exists and notify the admin."""
        if room_name in self.rooms:
            del self.rooms[room_name]
            self.broadcast(f"Room '{room_name}' has been deleted.", None)
            client_socket.send(f"Room '{room_name}' deleted successfully.".encode('utf-8'))
            logging.info(f"Room {room_name} deleted")
        else:
            client_socket.send(f"Room '{room_name}' does not exist.".encode('utf-8'))
            logging.warning(f"Attempt to delete non-existent room '{room_name}'")

    def private_message(self, sender, recipient, message):
        if recipient in self.clients:
            self.clients[recipient].send(f"Private message from {sender}: {message}".encode('utf-8'))
            logging.info(f"Private message sent from {sender} to {recipient}")
        else:
            self.clients[sender].send("User not found.".encode('utf-8'))
            logging.info(f"Failed to send private message from {sender} to {recipient} (user not found)")

    def create_room(self, username, room_name):
        if room_name not in self.rooms:
            self.rooms[room_name] = [username]
            self.clients[username].send(f"Room '{room_name}' created successfully.".encode('utf-8'))
            logging.info(f"Room {room_name} created by {username}")
        else:
            self.clients[username].send(f"Room '{room_name}' already exists.".encode('utf-8'))
            logging.info(f"User {username} attempted to create existing room {room_name}")

    def list_rooms(self, client_socket):
        room_list = ", ".join(self.rooms.keys())
        client_socket.send(f"Available rooms: {room_list}".encode('utf-8'))
        logging.info(f"Room list sent to client")

    def broadcast(self, message, sender_username):
        for client_username, client_socket in self.clients.items():
            if client_username != sender_username:
                client_socket.send(message.encode('utf-8'))
        logging.info(f"Broadcast message sent: {message}")

    def remove_client(self, username):
        if username in self.clients:
            logging.info(f"Removing {username}")
            self.clients[username].close()
            del self.clients[username]
            self.broadcast(f"{username} left the chat.", None)
        else:
            logging.warning(f"Attempted to remove non-existent client {username}")

if __name__ == "__main__":
    try:
        server = ChatServer()
        server.start()
    except Exception as e:
        logging.critical(f"Critical error: {e}", exc_info=True)
