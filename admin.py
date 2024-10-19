import socket
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog
import pyttsx3
from plyer import notification
from datetime import datetime, timedelta
import json
import os

class AdminClient:
    def __init__(self, host='localhost', port=5555):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.username = None
        self.dark_mode_enabled = False
        self.notification_sound_enabled = True
        self.notification_timeout = 5  # Default notification display time
        self.muted_users_file = "muted_users.json"
        self.muted_users = self.load_muted_users()

        self.engine = pyttsx3.init()

        # Set up the login window
        self.root = tk.Tk()
        self.root.title("Admin Login - Chat Messenger App")
        self.root.geometry("300x200")
        self.create_login_widgets()

    def create_login_widgets(self):
        tk.Label(self.root, text="Username:").pack(pady=5)
        self.username_entry = tk.Entry(self.root)
        self.username_entry.pack(pady=5)

        tk.Label(self.root, text="Password:").pack(pady=5)
        self.password_entry = tk.Entry(self.root, show="*")
        self.password_entry.pack(pady=5)

        tk.Button(self.root, text="Login", command=self.login).pack(pady=10)

    def login(self):
        self.username = self.username_entry.get()
        password = self.password_entry.get()

        try:
            self.socket.connect((self.host, self.port))
            print("Connected to server.")

            # Send admin choice
            self.socket.send("admin".encode('utf-8'))

            # Send username
            self.socket.recv(1024)  # Receive username prompt
            self.socket.send(self.username.encode('utf-8'))

            # Send password
            self.socket.recv(1024)  # Receive password prompt
            self.socket.send(password.encode('utf-8'))

            # Check authentication result
            result = self.socket.recv(1024).decode('utf-8')
            if "failed" in result.lower():
                messagebox.showerror("Error", "Authentication failed.")
                self.root.quit()
            else:
                messagebox.showinfo("Success", "Login successful!")
                self.root.destroy()
                self.start_admin_interface()
        except Exception as e:
            messagebox.showerror("Error", f"Connection error: {e}")
            self.root.quit()

    def start_admin_interface(self):
        self.speak_welcome()
        self.create_admin_window()

    def speak_welcome(self):
        welcome_message = f"Welcome {self.username} to Chat Messenger App!"
        self.engine.say(welcome_message)
        self.engine.runAndWait()

    def create_admin_window(self):
        self.admin_window = tk.Tk()
        self.admin_window.title("Admin Interface - Chat Messenger App")
        self.admin_window.geometry("600x500")

        # Dark mode toggle
        self.dark_mode_var = tk.IntVar(value=0)
        self.dark_mode_button = tk.Checkbutton(self.admin_window, text="Enable Dark Mode",
                                               variable=self.dark_mode_var, command=self.toggle_dark_mode)
        self.dark_mode_button.pack(pady=10)

        # Notification settings
        self.notification_settings_button = tk.Button(self.admin_window, text="Notification Settings", command=self.show_notification_settings)
        self.notification_settings_button.pack(pady=10)

        # Create a frame for the radio buttons
        self.menu_frame = tk.Frame(self.admin_window)
        self.menu_frame.pack(pady=10)

        # Create radio buttons for menu options
        self.menu_var = tk.StringVar()
        self.menu_var.set("none")  # Initialize with no selection

        menu_options = [
            ("Kick User", "kick"),
            ("Ban User", "ban"),
            ("Temp Ban", "temp_ban"),
            ("Mute User", "mute"),
            ("Unmute User", "unmute"),
            ("List Users", "list_users"),
            ("Create Room", "create_room"),
            ("Delete Room", "delete_room"),
            ("List Rooms", "list_rooms"),
            ("Broadcast to Room", "broadcast_room"),
            ("Send Message", "send_message"),
            ("Personal Message", "personal_message"),
            ("Exit", "exit")  # Add the Exit option
        ]

        # Create radio buttons in a grid layout
        for i, (text, value) in enumerate(menu_options):
            tk.Radiobutton(self.menu_frame, text=text, variable=self.menu_var, value=value,
                           command=self.handle_menu_selection).grid(row=i//3, column=i%3, sticky="w", padx=10, pady=5)

        # Message display area
        self.message_frame = tk.Frame(self.admin_window)
        self.message_frame.pack(pady=10, expand=True, fill=tk.BOTH)

        self.message_text = tk.Text(self.message_frame, height=10, width=50)
        self.message_text.pack(expand=True, fill=tk.BOTH)

        # Input area for sending messages
        self.input_frame = tk.Frame(self.admin_window)
        self.input_frame.pack(pady=10, fill=tk.X)

        self.input_entry = tk.Entry(self.input_frame, width=50)
        self.input_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(10, 0))

        self.send_button = tk.Button(self.input_frame, text="Send", command=self.send_input)
        self.send_button.pack(side=tk.RIGHT, padx=10)

        # Start thread for receiving messages
        receive_thread = threading.Thread(target=self.receive_messages)
        receive_thread.daemon = True
        receive_thread.start()

        self.admin_window.mainloop()

    def toggle_dark_mode(self):
        """Toggle between light and dark mode themes."""
        if self.dark_mode_var.get() == 1:
            self.admin_window.config(bg="black")
            self.menu_frame.config(bg="black")
            self.message_text.config(bg="black", fg="white")
            self.input_entry.config(bg="black", fg="white")
        else:
            self.admin_window.config(bg="lightgray")
            self.menu_frame.config(bg="lightgray")
            self.message_text.config(bg="white", fg="black")
            self.input_entry.config(bg="white", fg="black")

    def show_notification_settings(self):
        """Open a dialog to allow customization of notification settings."""
        sound_choice = simpledialog.askstring("Notification Sound", "Enable sound? (yes/no):")
        if sound_choice and sound_choice.lower() == "no":
            self.notification_sound_enabled = False
        else:
            self.notification_sound_enabled = True

        timeout = simpledialog.askinteger("Notification Timeout", "Enter notification timeout in seconds:", initialvalue=self.notification_timeout)
        if timeout:
            self.notification_timeout = timeout

    def handle_menu_selection(self):
        selection = self.menu_var.get()
        if selection == "kick":
            self.kick_user()
        elif selection == "ban":
            self.ban_user()
        elif selection == "temp_ban":
            self.temp_ban_user()
        elif selection == "mute":
            self.mute_user()
        elif selection == "unmute":
            self.unmute_user()
        elif selection == "list_users":
            self.list_users()
        elif selection == "create_room":
            self.create_room()
        elif selection == "delete_room":
            self.delete_room()
        elif selection == "list_rooms":
            self.list_rooms()
        elif selection == "broadcast_room":
            self.broadcast_to_room()
        elif selection == "send_message":
            self.focus_input()
        elif selection == "personal_message":
            self.personal_message()
        elif selection == "exit":  # Handle the Exit selection
            self.exit_application()

    # User management functions
    def kick_user(self):
        username = simpledialog.askstring("Kick User", "Enter username to kick:")
        if username:
            self.send_message(f"/kick {username}")

    def ban_user(self):
        username = simpledialog.askstring("Ban User", "Enter username to ban:")
        if username:
            self.send_message(f"/ban {username}")

    def temp_ban_user(self):
        username = simpledialog.askstring("Temporary Ban", "Enter username to ban:")
        if username:
            duration = simpledialog.askinteger("Temporary Ban", "Enter ban duration in minutes:")
            if duration:
                self.send_message(f"/temp_ban {username} {duration}")

    def mute_user(self):
        username = simpledialog.askstring("Mute User", "Enter username to mute:")
        if username:
            duration = simpledialog.askinteger("Mute User", "Enter mute duration in minutes:")
            if duration:
                mute_end_time = datetime.now() + timedelta(minutes=duration)
                self.muted_users[username] = mute_end_time
                self.send_message(f"/mute {username} {duration}")
                self.save_muted_users()

    def unmute_user(self):
        username = simpledialog.askstring("Unmute User", "Enter username to unmute:")
        if username in self.muted_users:
            del self.muted_users[username]
            self.send_message(f"/unmute {username}")
            self.save_muted_users()

    def list_users(self):
        """Send a request to list all users."""
        self.send_message("/list_users")

    # Room management
    def create_room(self):
        room_name = simpledialog.askstring("Create Room", "Enter room name:")
        if room_name:
            self.send_message(f"/create_room {room_name}")

    def delete_room(self):
        room_name = simpledialog.askstring("Delete Room", "Enter room name to delete:")
        if room_name:
            self.send_message(f"/delete_room {room_name}")

    def list_rooms(self):
        self.send_message("/list_rooms")

    def broadcast_to_room(self):
        room_name = simpledialog.askstring("Broadcast to Room", "Enter room name:")
        if room_name:
            message = simpledialog.askstring("Broadcast to Room", "Enter message to broadcast:")
            if message:
                self.send_message(f"/broadcast_room {room_name} {message}")

    # Messaging features
    def personal_message(self):
        recipient = simpledialog.askstring("Personal Message", "Enter recipient's username:")
        if recipient:
            message = simpledialog.askstring("Personal Message", f"Enter message for {recipient}:")
            if message:
                self.send_message(f"/pm {recipient} {message}")

    def focus_input(self):
        self.input_entry.focus_set()

    def save_muted_users(self):
        """Save muted users and their mute expiration times to a file."""
        with open(self.muted_users_file, "w") as f:
            json.dump({user: mute_end.isoformat() for user, mute_end in self.muted_users.items()}, f)

    def load_muted_users(self):
        """Load muted users from a file."""
        if os.path.exists(self.muted_users_file):
            with open(self.muted_users_file, "r") as f:
                muted_data = json.load(f)
                return {user: datetime.fromisoformat(mute_end) for user, mute_end in muted_data.items()}
        return {}

    def send_input(self):
        message = self.input_entry.get()
        if message:
            self.send_message(message)
            self.input_entry.delete(0, tk.END)

    def send_message(self, message):
        try:
            self.socket.send(message.encode('utf-8'))
        except Exception as e:
            messagebox.showerror("Error", f"Error sending message: {e}")

    # Receiving messages and notifications
    def receive_messages(self):
        while True:
            try:
                message = self.socket.recv(1024).decode('utf-8')
                if message:
                    self.message_text.insert(tk.END, message + "\n")
                    self.message_text.see(tk.END)
                    self.show_desktop_notification(message)
                else:
                    messagebox.showinfo("Info", "Connection closed by the server.")
                    break
            except Exception as e:
                messagebox.showerror("Error", f"Error receiving message: {e}")
                break

    def show_desktop_notification(self, message):
        notification.notify(
            title="New Message",
            message=message,
            timeout=self.notification_timeout
        )
        if self.notification_sound_enabled:
            self.engine.say("You have a new message.")
            self.engine.runAndWait()

    def exit_application(self):
        if messagebox.askyesno("Exit", "Are you sure you want to exit?"):
            try:
                self.send_message("/quit")
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except OSError as e:
                print(f"Socket error during shutdown: {e}")
            finally:
                self.socket=None
            self.admin_window.destroy()

    def start(self):
        self.root.mainloop()

if __name__ == "__main__":
    admin = AdminClient()
    admin.start()
