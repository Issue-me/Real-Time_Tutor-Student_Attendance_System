import socket
import threading
import time
from datetime import datetime
import tkinter as Tkinter
from tkinter import scrolledtext

# Class declaration that uses the tutor server
class TutorServer:
    def __init__(self, gui, host='127.0.0.1', port=5000):
        self.gui = gui  # Reference to the GUI
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((host, port))
        self.server_socket.listen(30)  # Max 30 students
        self.students = {}  # Declares students
        self.student_sockets = {}  # Initialize the student sockets dictionary
        self.lock = threading.Lock()  # Locks the thread
        self.session_duration = 30 * 60  # 30 minutes in seconds
        self.session_end_time = None  # Session ending time
        self.session_active = False  # Track if the session is active

    # Function declaration on handling the clients socket and port address
    def handle_client(self, client_socket, addr):
        print(f"Connection from {addr} has been established.")
        while True:  # While the connection is still connected
            try:
                message = client_socket.recv(1024).decode('utf-8')  # Decoding the client's socket
                if not message:
                    break
                if "has exited the session" in message:
                    self.notify_exit(message)
                else:
                    self.process_message(message, client_socket, addr)
            except ConnectionResetError:  # When there is a connection error
                break
        client_socket.close()  # Closes the connection

    # Notify all tutors about the student's exit
    def notify_exit(self, message):
        print(message)  # Log the exit message
        student_id = message.split()[1]  # Extract student ID from the message
        with self.lock:
            if student_id in self.students:
                del self.students[student_id]  # Remove student from the list
                if student_id in self.student_sockets:
                    del self.student_sockets[student_id]  # Remove socket from the mapping
        self.broadcast_message(f"{student_id} has exited the session.")
        self.gui.update_attendance_display()  # Update attendance in GUI

    # Processes the messages (student's name and id)
    def process_message(self, message, client_socket, addr):
        parts = message.split(';')
        student_id = parts[0].split(':')[1].strip()
        student_name = parts[1].split(':')[1].strip()

        with self.lock:
            self.students[student_id] = student_name  # Store name
            self.student_sockets[student_id] = client_socket  # Store the socket in the mapping
            print(f"Student checked in: {student_name} (ID: {student_id})")
            self.send_acknowledgment(client_socket)  # Sends acknowledgment across to the client (student)

        self.gui.update_attendance_display()  # Update attendance in GUI

        # Start the session timer if it's the first student checking in
        if len(self.students) == 1 and not self.session_active:
            self.session_end_time = time.time() + self.session_duration
            self.session_active = True
            threading.Thread(target=self.session_timer).start()

    # Sends the acknowledgment to the client/student
    def send_acknowledgment(self, client_socket):
        timestamp = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        ack_message = f"Check-in acknowledged at {timestamp}"
        client_socket.send(ack_message.encode('utf-8'))

    # Session timer of 30 minutes
    def session_timer(self):
        while time.time() < self.session_end_time:
            time.sleep(1)
        self.notify_end_of_session()  # Notifies the students in the session that the session has ended

    # Notification for the end of session
    def notify_end_of_session(self):
        self.session_active = False
        self.broadcast_message("The session has ended.")
        self.gui.update_attendance_display()  # Update attendance in GUI

    # Sends the message across to its clients/students
    def broadcast_message(self, message):
        with self.lock:  # Ensure thread safety when accessing shared resources
            for student_id, student_name in list(self.students.items()):  # Use list to avoid modifying the dict during iteration
                try:
                    if student_id in self.student_sockets:
                        socket = self.student_sockets[student_id]
                        if socket:  # Check if the socket is still valid
                            socket.send(message.encode('utf-8'))
                except Exception as e:
                    print(f"Failed to send message to {student_name}: {e}")
                    # Remove the student from the lists if the socket is invalid
                    with self.lock:
                        del self.students[student_id]
                        del self.student_sockets[student_id]

    # Displays the message when the server is running
    def start(self):
        print("Tutor Server is running...")
        while True:
            client_socket, addr = self.server_socket.accept()
            threading.Thread(target=self.handle_client, args=(client_socket, addr)).start()

# GUI for the Tutor
class TutorGUI:
    def __init__(self, server):
        self.server = server
        self.root = Tkinter.Tk()
        self.root.title("Tutor Control Panel")
        self.session_active = False

        self.start_button = Tkinter.Button(self.root, text="Start Session", command=self.start_session)
        self.start_button.pack(pady=10)

        self.end_button = Tkinter.Button(self.root, text="End Session", command=self.end_session)
        self.end_button.pack(pady=10)

        self.attendance_display = scrolledtext.ScrolledText(self.root, width=40, height=10)
        self.attendance_display.pack(pady=10)

        self.timer_label = Tkinter.Label(self.root, text="Session Timer: Not Started")
        self.timer_label.pack(pady=10)

        self.update_timer_thread = None

    def start_session(self):
        if not self.server.session_active:
            # Start the server in a new thread
            threading.Thread(target=self.server.start, daemon=True).start()
            self.server.session_end_time = time.time() + self.server.session_duration  # Set session end time
            self.server.session_active = True  # Set session active
            self.update_timer_thread = threading.Thread(target=self.update_timer)
            self.update_timer_thread.start()

    def end_session(self):
        if self.server.session_active:
            self.server.notify_end_of_session()
            self.timer_label.config(text="Session Timer: Not Started")  # Reset timer label
            self.update_attendance_display()  # Update attendance display
            self.server.session_active = False  # Set session inactive

    def update_timer(self):
        while self.server.session_active:
            remaining_time = self.server.session_end_time - time.time()
            if remaining_time > 0:
                minutes, seconds = divmod(int(remaining_time), 60)
                self.timer_label.config(text=f"Session Timer: {minutes:02}:{seconds:02}")
            else:
                self.timer_label.config(text="Session Timer: Time's Up!")
                break
            time.sleep(1)

    def update_attendance_display(self):
        attendance_message = "Current Attendance:\n"
        for student_id, student_name in self.server.students.items():
            attendance_message += f"ID: {student_id}, Name: {student_name}\n"
        self.attendance_display.delete(1.0, Tkinter.END)
        self.attendance_display.insert(Tkinter.END, attendance_message)

# Main function
if __name__ == "__main__":
    gui = TutorGUI(None)
    server = TutorServer(gui)
    gui.server = server
    gui.root.mainloop()