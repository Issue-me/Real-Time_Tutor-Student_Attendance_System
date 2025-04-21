import socket
import threading
import tkinter as Tkinter
import tkinter.scrolledtext as ScrolledText
from tkinter import messagebox
from tkinter import simpledialog

# Declares a student client
class StudentClient:
    
    # Sets the port number and port address of the client
    def __init__(self, host='127.0.0.1', port=5000):
        self.server_address = (host, port)
        self.peer_port = None
        self.root = Tkinter.Tk()
        self.root.title("Student Client")
        self.create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.peer_socket = None  # To keep track of the peer socket
        self.listening = True  # Flag to control the listening loop

    def create_widgets(self):
        # Frame for input
        input_frame = Tkinter.Frame(self.root)
        input_frame.pack(pady=10)

        Tkinter.Label(input_frame, text="Student ID:").grid(row=0, column=0)
        
        # Create a validation command for digits
        validate_id = self.root.register(self.validate_digit_input)
        
        self.student_id_entry = Tkinter.Entry(input_frame, validate="key", validatecommand=(validate_id, '%S'))
        self.student_id_entry.grid(row=0, column=1)

        # First Name Entry
        Tkinter.Label(input_frame, text="First Name:").grid(row=1, column=0)
        self.first_name_entry = Tkinter.Entry(input_frame)
        self.first_name_entry.grid(row=1, column=1)

        # Last Name Entry
        Tkinter.Label(input_frame, text="Last Name:").grid(row=2, column=0)
        self.last_name_entry = Tkinter.Entry(input_frame)
        self.last_name_entry.grid(row=2, column=1)

        self.check_in_button = Tkinter.Button(input_frame, text="Check In", command=self.check_in)
        self.check_in_button.grid(row=3, columnspan=2)

        # Text area for displaying messages
        self.history = ScrolledText.ScrolledText(self.root, width=50, height=15, state='disabled')
        self.history.pack(pady=10)

        # Frame for chat
        chat_frame = Tkinter.Frame(self.root)
        chat_frame.pack(pady=10)

        Tkinter.Label(chat_frame, text="Peer IP:").grid(row=0, column=0)
        self.peer_ip_entry = Tkinter.Entry(chat_frame)
        self.peer_ip_entry.grid(row=0, column=1)

        Tkinter.Label(chat_frame, text="Peer Port:").grid(row=1, column=0)
        self.peer_port_entry = Tkinter.Entry(chat_frame)
        self.peer_port_entry.grid(row=1, column=1)

        self.send_button = Tkinter.Button(chat_frame, text="Send Message", command=self.start_chat)
        self.send_button.grid(row=2, columnspan=2)

        # Exit Session Button
        self.exit_button = Tkinter.Button(chat_frame, text="Exit Session", command=self.exit_session)
        self.exit_button.grid(row=3, columnspan=2)

    # Validation function to allow only digits for Student ID
    def validate_digit_input(self, char):
        return char.isdigit()  # Allow only digits

    # Validation function for names
    def validate_name(self, name):
        return name.isalpha()  # Allow only alphabetic characters

    # Checks the student in to the tutorial session
    def check_in(self):
        student_id = self.student_id_entry.get()
        first_name = self.first_name_entry.get()
        last_name = self.last_name_entry.get()
        
        if not student_id or not first_name or not last_name:
            messagebox.showwarning("Input Error", "Please enter Student ID, First Name, and Last Name.")
            return
        
        if not self.validate_name(first_name) or not self.validate_name(last_name):
            messagebox.showwarning("Input Error", "Names must contain only alphabetic characters.")
            return

        message = f"ID: {student_id}; Name: {first_name} {last_name}"
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                client_socket.connect(self.server_address)
                client_socket.send(message.encode('utf-8'))

                # Attempt to receive acknowledgment with error handling
                for attempt in range(3):  # Retry up to 3 times
                    try:
                        ack = client_socket.recv(1024).decode('utf-8')
                        if ack:
                            self.display_message(ack)
                            break  # Exit the retry loop on success
                    except ConnectionAbortedError:
                        if attempt < 2:  # If not the last attempt, retry
                            self.display_message("Connection was aborted by the host machine. Retrying...")
                        else:
                            self.display_message("Max retries reached. Please check the server status.")
                            return
                    except Exception as e:
                        self.display_message(f"An error occurred: {e}")
                        return

        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not connect to the server: {e}")

        # Start listening for messages from the tutor
        threading.Thread(target=self.listen_for_messages, daemon=True).start()

    # Listens to the messages sent by the tutor
    def listen_for_messages(self):
        self.peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.peer_socket.bind(('0.0.0.0', 0))  # Bind to any available port
        self.peer_port = self.peer_socket.getsockname()[1]
        self.display_message(f"Listening for messages on port {self.peer_port}")
        self.peer_socket.listen(5)

        while self.listening:
            try:
                conn, addr = self.peer_socket.accept()
                threading.Thread(target=self.handle_message_from_peer, args=(conn, addr)).start()
            except OSError:
                break  # Exit the loop if the socket is closed

    # Handles the messages from the client/student
    def handle_message_from_peer(self, conn, addr):
        while True:
            try:
                message = conn.recv(1024).decode('utf-8')
                if not message:
                    break
                self.display_message(f"Message from {addr}: {message}")
            except ConnectionResetError:
                break
        conn.close()

    # Starts the chat of the clients/students
    def start_chat(self):
        peer_ip = self.peer_ip_entry.get()
        try:
            peer_port = int(self.peer_port_entry.get())
            message = self.get_message()
            self.send_message_to_peer(peer_ip, peer_port, message)
        except ValueError:
            messagebox.showerror("Input Error", "Please enter a valid port number.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # Sends the message across to the other clients/students
    def send_message_to_peer(self, peer_ip, peer_port, message):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as peer_socket:
                peer_socket.connect((peer_ip, peer_port))
                peer_socket.send(message.encode('utf-8'))
                self.display_message(f"Message sent to {peer_ip}:{peer_port}")
                
                # Clear the IP and port entries after sending the message
                self.peer_ip_entry.delete(0, 'end')  # Clear the IP entry
                self.peer_port_entry.delete(0, 'end')  # Clear the port entry
                
        except socket.gaierror:
            messagebox.showerror("Connection Error", f"Failed to connect to {peer_ip}:{peer_port}.")
        except ConnectionRefusedError:
            messagebox.showerror("Connection Error", f"Connection refused by {peer_ip}:{peer_port}.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # Displays messages in the text area
    def display_message(self, message):
        self.history.config(state='normal')
        self.history.insert('end', f"{message}\n")
        self.history.config(state='disabled')
        self.history.yview('end')  # Scroll to the end

    # Gets the message from the user input
    def get_message(self):
        message = Tkinter.simpledialog.askstring("Input", "Enter your message:")
        return message if message else ""

    # Handles window closing
    def on_closing(self):
        self.exit_session()

    # Exits the session and closes sockets
    def exit_session(self):
        self.listening = False  # Stop the listening loop
        if self.peer_socket:
            self.peer_socket.close()
        self.notify_tutor_exit()  # Notify the tutor about the exit
        self.root.destroy()

    # Notify the tutor that the student is exiting
    def notify_tutor_exit(self):
        exit_message = f"Student {self.student_id_entry.get()} has exited the session."
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect(self.server_address)
            client_socket.send(exit_message.encode('utf-8'))

# Main function
if __name__ == "__main__":
    client = StudentClient()
    client.root.mainloop()