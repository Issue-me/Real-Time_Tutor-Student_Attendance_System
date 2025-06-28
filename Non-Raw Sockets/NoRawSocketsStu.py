import socket #for communication using sockets
import threading #runs background tasks
import tkinter as Tkinter #student's GUI
import tkinter.scrolledtext as ScrolledText #for scrolling
from tkinter import messagebox, simpledialog #for dialog boxes, warnings, input

#student class
class StudentClient:
    #function initialization for attributes and student's windows
    def __init__(self, host='127.0.0.1', port=5000):
        self.server_address = (host, port)
        self.root = Tkinter.Tk()
        self.root.title("Student Client")

        self.client_socket = None  #server socket
        self.is_checked_in = False
        self.student_id = None
        self.student_name = None

        #student-to-student attributes
        self.peer_listener = None
        self.peer_listen_port = None
        self.peer_listen_thread = None
        self.peer_connections = []  #list of connected student sockets
        self.create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    #function for student's GUI
    def create_widgets(self):
        input_frame = Tkinter.Frame(self.root)
        input_frame.pack(pady=10)

        Tkinter.Label(input_frame, text="Student ID:").grid(row=0, column=0)
        validate_id = self.root.register(self.validate_digit_input)
        self.student_id_entry = Tkinter.Entry(input_frame, validate="key", validatecommand=(validate_id, '%S'))
        self.student_id_entry.grid(row=0, column=1)

        Tkinter.Label(input_frame, text="First Name:").grid(row=1, column=0)
        self.first_name_entry = Tkinter.Entry(input_frame)
        self.first_name_entry.grid(row=1, column=1)

        Tkinter.Label(input_frame, text="Last Name:").grid(row=2, column=0)
        self.last_name_entry = Tkinter.Entry(input_frame)
        self.last_name_entry.grid(row=2, column=1)

        self.check_in_button = Tkinter.Button(input_frame, text="Check In", command=self.check_in)
        self.check_in_button.grid(row=3, columnspan=2)

        #stores the chat history
        self.history = ScrolledText.ScrolledText(self.root, width=60, height=10, state='disabled')
        self.history.pack(pady=5)

        #stores the attendance list
        attendance_frame = Tkinter.Frame(self.root)
        attendance_frame.pack(pady=5)

        Tkinter.Label(attendance_frame, text="Attendance List:").pack()

        self.attendance_list = ScrolledText.ScrolledText(attendance_frame, width=60, height=10, state='disabled')
        self.attendance_list.pack()
        
        # session timer label for students
        self.timer_label = Tkinter.Label(self.root, text="Session Timer: Not Started")
        self.timer_label.pack(pady=5)


        #chat input frame for students
        chat_frame = Tkinter.Frame(self.root)
        chat_frame.pack(pady=10)

        Tkinter.Label(chat_frame, text="Peer IP:").grid(row=0, column=0)
        self.peer_ip_entry = Tkinter.Entry(chat_frame)
        self.peer_ip_entry.grid(row=0, column=1)
        self.peer_ip_entry.insert(0, '127.0.0.1')

        Tkinter.Label(chat_frame, text="Peer Port:").grid(row=1, column=0)
        self.peer_port_entry = Tkinter.Entry(chat_frame)
        self.peer_port_entry.grid(row=1, column=1)

        self.send_button = Tkinter.Button(chat_frame, text="Send Message", command=self.start_chat, state='disabled')
        self.send_button.grid(row=2, columnspan=2)

        self.exit_button = Tkinter.Button(chat_frame, text="Exit Session", command=self.exit_session)
        self.exit_button.grid(row=3, columnspan=2)

    #function that validates the student id
    def validate_digit_input(self, char):
        return char.isdigit() and len(self.student_id_entry.get()) < 5

    #function that updates the attendance
    def update_attendance_list(self, raw_data):
        self.attendance_list.config(state='normal')
        
        #clear previous attendance records
        self.attendance_list.delete('1.0', 'end')  

        #header
        self.attendance_list.insert('end', f"{'PORT':<10} {'ID':<10} {'NAME':<30}\n")
        self.attendance_list.insert('end', "-" * 50 + "\n")

        if raw_data.strip():
            entries = raw_data.split(",")
            for entry in entries:
                try:
                    port, student_id, name = entry.strip().split("-")
                    self.attendance_list.insert('end', f"{port:<10} {student_id:<10} {name:<30}\n")
                except ValueError:
                    continue  #skips malformed entries

        self.attendance_list.config(state='disabled')
        self.attendance_list.yview('end')

    #function for check in system
    def check_in(self):
        student_id = self.student_id_entry.get()
        first_name = self.first_name_entry.get()
        last_name = self.last_name_entry.get()

        #if student id is longer than 5 digits
        if len(student_id) != 5:
            messagebox.showwarning("Input Error", "Student ID must be exactly 5 digits long.")
            return

        #if name is not in alphabetical letters
        if not first_name.isalpha() or not last_name.isalpha():
            messagebox.showwarning("Input Error", "First and Last Name must contain only alphabetic characters.")
            return

        #automatically assigns student listening port based on last two digits of student ID
        self.peer_listen_port = 6000 + int(student_id[-2:])  #set listen port first
        message = f"ID: {student_id}; Name: {first_name} {last_name}; Port: {self.peer_listen_port}"

        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect(self.server_address)
            self.client_socket.send(message.encode('utf-8'))

            response = self.client_socket.recv(1024).decode('utf-8')
            if response:
                if "Maximum number of students reached" in response or "must be unique" in response:
                    messagebox.showwarning("Check-in Error", response)
                    self.exit_session()
                    return
                else:
                    self.display_message(response)
                    self.is_checked_in = True
                    self.student_id = student_id
                    self.student_name = f"{first_name} {last_name}"
                    self.send_button.config(state='normal')

            if self.is_checked_in:
                threading.Thread(target=self.listen_for_server_messages, daemon=True).start()

            self.start_peer_listener(self.peer_listen_port)  #start listener after sending

        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not connect to the server: {e}")

    #function that listens to server messages
    def listen_for_server_messages(self):
        while True:
            try:
                message = self.client_socket.recv(1024).decode('utf-8')
                if message:
                    if message.startswith("ATTENDANCE_LIST:"):
                        attendance_data = message.replace("ATTENDANCE_LIST:", "")
                        self.update_attendance_list(attendance_data)
                    elif message.startswith("TIMER_UPDATE:"):
                        timer_time = message.split(":")[1] + ":" + message.split(":")[2]
                        self.timer_label.config(text=f"Session Timer: {timer_time}")
                    else:
                        self.display_message(f"Tutor: {message}")
                else:
                    self.display_message("Disconnected from server.")
                    break
            except Exception as e:
                self.display_message(f"Error receiving message from server: {e}")
                break

    #function that starts listening to student's messages
    def start_peer_listener(self, port):
        def listen():
            self.peer_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.peer_listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.peer_listener.bind(('', port))
            self.peer_listener.listen(5)
            self.display_message(f"Listening for peer connections on port {port}...")
            while True:
                try:
                    peer_conn, peer_addr = self.peer_listener.accept()
                    self.peer_connections.append(peer_conn)
                    threading.Thread(target=self.handle_peer_connection, args=(peer_conn, peer_addr), daemon=True).start()
                except Exception:
                    break

        self.peer_listen_thread = threading.Thread(target=listen, daemon=True)
        self.peer_listen_thread.start()

    #function that handles the student's connection
    def handle_peer_connection(self, peer_conn, peer_addr):
        self.display_message(f"Peer connected from {peer_addr}")
        while True:
            try:
                data = peer_conn.recv(1024)
                if not data:
                    break
                message = data.decode('utf-8')
                self.display_message(f"Peer [{peer_addr}]: {message}")
            except Exception:
                break
        peer_conn.close()
        self.peer_connections.remove(peer_conn)
        self.display_message(f"Peer disconnected: {peer_addr}")

    #function that starts chatting with other students
    def start_chat(self):
        peer_ip = self.peer_ip_entry.get().strip()
        peer_port_str = self.peer_port_entry.get().strip()

        if not peer_ip:
            messagebox.showwarning("Invalid Input", "Please enter a peer IP address.")
            return
        if not peer_port_str.isdigit():
            messagebox.showwarning("Invalid Input", "Please enter a valid peer port number.")
            return

        peer_port = int(peer_port_str)
        message = self.get_message()
        if not message:
            return
            
        if peer_port == self.peer_listen_port:
            messagebox.showerror("Invalid", "Cannot send message to yourself!")
            return

        threading.Thread(target=self.send_message_to_peer, args=(peer_ip, peer_port, message), daemon=True).start()

    #function that sends messages across to other students
    def send_message_to_peer(self, peer_ip, peer_port, message):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as peer_socket:
                peer_socket.connect((peer_ip, peer_port))
                peer_socket.send(message.encode('utf-8'))
                self.display_message(f"Message sent to {peer_ip}:{peer_port}")
        except Exception as e:
            messagebox.showerror("Peer Connection Error", f"Failed to send message to {peer_ip}:{peer_port}\n{e}")

    #function that displays messages in the student's GUI
    def display_message(self, message):
        self.history.config(state='normal')
        self.history.insert('end', message + '\n')
        self.history.config(state='disabled')
        self.history.yview('end')

    #function that gets the message from the student
    def get_message(self):
        # Prompt user to enter message
        message = simpledialog.askstring("Send Message", "Enter your message:")
        if not message:
            messagebox.showinfo("No Message", "You didn't enter any message.")
            return None
        return message

    #function that exists the session
    def on_closing(self):
        self.exit_session()

    #function that exists the session and closes the student's GUI
    def exit_session(self):
        if self.client_socket:
            try:
                self.client_socket.send("EXIT".encode('utf-8'))
                self.client_socket.close()
            except:
                pass

        for conn in self.peer_connections:
            try:
                conn.close()
            except:
                pass
        self.peer_connections.clear()

        if self.peer_listener:
            try:
                self.peer_listener.close()
            except:
                pass
        self.root.destroy()

#main function
if __name__ == "__main__":
    client = StudentClient()
    client.root.mainloop()
