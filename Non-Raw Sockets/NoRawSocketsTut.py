import socket
import threading #for polling (not freezing tutor's GUI)
import time #for using session timers and delays
from datetime import datetime #for timestamps for attendance files
import tkinter as Tkinter #tutor's GUI
from tkinter import scrolledtext #for scrolling

#log attendance in a txt file
ATTENDANCE_LOG_FILE = "attendance_log.txt"

#function that logs the attendance into a file
def log_attendance(message):
    timestamp = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    with open(ATTENDANCE_LOG_FILE, "a") as f:
        f.write(f"{timestamp} - {message}\n")

#class for user authentication
class UserAuthentication:
    #initialization
    def __init__(self):
        self.sessions = {}  #dictionary to store active sessions

    #function that validates the student id
    def is_unique_student_id(self, student_id):
        return student_id not in self.sessions.values()

#tutor server's class
class TutorServer:
    #initialization
    def __init__(self, gui, host='127.0.0.1', port=5000):
        self.gui = gui
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((host, port))
        self.server_socket.listen(3) #only 3 students allowed in a session
        self.students = {}  # {student_id: (student_name, port)}
        self.student_sockets = {}  # {student_id: socket}
        self.lock = threading.Lock()
        self.session_duration = 6 * 60  # 6 minutes session (testing)
        self.session_end_time = None
        self.session_active = False
        self.warning_sent = False
        self.auth = UserAuthentication()

    #function that handles the clients
    def handle_client(self, client_socket, addr):
        print(f"Connection from {addr} established.")
        while True:
            try:
                message = client_socket.recv(1024).decode('utf-8')
                if not message:
                    break
                if "has exited the session" in message:
                    self.notify_exit(message)
                else:
                    self.process_message(message, client_socket, addr)
            except ConnectionResetError:
                print(f"Connection reset by {addr}.")
                break
            except Exception as e:
                print(f"Error handling client {addr}: {e}")
                break
        client_socket.close()
        with self.lock:
            for student_id, sock in list(self.student_sockets.items()):
                if sock == client_socket:
                    del self.student_sockets[student_id]
                    del self.students[student_id]
                    log_attendance(f"Student {student_id} disconnected unexpectedly.")
                    break
        self.gui.update_attendance_display()
        self.broadcast_attendance_list()  # <- Add this line to notify remaining students

    #function that sends the message across to all students
    def broadcast_message(self, message):
        with self.lock:
            for student_id in list(self.students.keys()):
                try:
                    sock = self.student_sockets.get(student_id)
                    if sock:
                        sock.send(message.encode('utf-8'))
                        print(f"Sent to {self.students[student_id]} (ID: {student_id}): {message}")
                except Exception as e:
                    print(f"Failed to send message to {student_id}: {e}")
                    del self.students[student_id]
                    del self.student_sockets[student_id]
                    self.gui.update_attendance_display()

    #function that notifies the tutor of the student's exit
    def notify_exit(self, message):
        print(message)
        student_id = message.split()[1]
        with self.lock:
            if student_id in self.students:
                log_attendance(f"Student {student_id} ({self.students[student_id]}) has exited the session.")
                del self.students[student_id]
            if student_id in self.student_sockets:
                del self.student_sockets[student_id]
        self.broadcast_message(f"{student_id} has exited the session.")
        self.gui.update_attendance_display()
        self.broadcast_attendance_list()  # broadcast updated list here

    #function that sends the attendance list to every student
    def broadcast_attendance_list(self):
        attendance_list = []
        for student_id, (student_name, port) in self.students.items():
            attendance_list.append(f"{port}-{student_id}-{student_name}")
        attendance_message = "ATTENDANCE_LIST:" + ",".join(attendance_list)
        self.broadcast_message(attendance_message)

    #function that processes the messages to the students
    def process_message(self, message, client_socket, addr):
        try:
            parts = message.split(';')
            if len(parts) < 3:
                print(f"Ignoring malformed message (not enough parts): {message}")
                return

            student_id = parts[0].split(':')[1].strip()
            student_name = parts[1].split(':')[1].strip()
            student_listen_port = parts[2].split(':')[1].strip()  #student's actual listening port

        except (IndexError, ValueError) as e:
            print(f"Malformed message received: {message} — Error: {e}")
            return

        with self.lock:
            if student_id in self.students:
                error_message = "Student ID must be unique."
                client_socket.send(error_message.encode('utf-8'))
                return
            if len(self.students) >= 3:
                error_message = "Maximum number of students reached. Cannot check in."
                client_socket.send(error_message.encode('utf-8'))
                return

            self.students[student_id] = (student_name, student_listen_port)
            self.student_sockets[student_id] = client_socket
            log_attendance(f"Student checked in: {student_id} - {student_name} (Port: {student_listen_port})")
            print(f"Student checked in: {student_name} (ID: {student_id}) on port {student_listen_port}")
            self.send_acknowledgment(client_socket)

        self.gui.update_attendance_display()
        self.broadcast_attendance_list()

        if len(self.students) == 1 and not self.session_active:
            self.session_end_time = time.time() + self.session_duration
            self.session_active = True
            self.warning_sent = False
            log_attendance("Session started.")
            threading.Thread(target=self.session_timer, daemon=True).start()
            threading.Thread(target=self.gui.update_timer, daemon=True).start()

    #function that sends the acknowledgment to all students upon checking in
    def send_acknowledgment(self, client_socket):
        timestamp = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        ack_message = f"Check-in acknowledged at {timestamp}"
        client_socket.send(ack_message.encode('utf-8'))

    #function that updates the session timer
    def session_timer(self):
        print("Session timer started.")
        while self.session_active:
            now = time.time()
            remaining = self.session_end_time - now

            if remaining <= 0:
                self.broadcast_message("The session has ended.")
                self.session_active = False
                log_attendance("Session ended.")
                self.gui.update_attendance_display()
                print("Session ended.")
                break
            
            remaining_minutes = int(remaining // 60)

            #send 5-minute warning once
            if int(remaining // 60) == 5 and int(remaining % 60) == 0 and not self.warning_sent:
                self.broadcast_message("Warning: 5 minutes remaining in the session!")
                print("Sent 5-minute warning.")
                log_attendance("Sent 5-minute warning.")
                self.warning_sent = True
            
            time.sleep(1)
            
            #broadcast the session timer update to students
            minutes, seconds = divmod(int(remaining), 60)
            timer_message = f"TIMER_UPDATE:{minutes:02}:{seconds:02}"
            self.broadcast_message(timer_message)

    #function that notifies that the session has ended
    def notify_end_of_session(self):
        self.session_active = False
        self.broadcast_message("The session has ended.")
        log_attendance("Session ended manually.")
        self.gui.update_attendance_display()

    #function that starts the server
    def start(self):
        print("Server is starting...")
        try:
            while True:
                try:
                    client_socket, addr = self.server_socket.accept()
                    threading.Thread(target=self.handle_client, args=(client_socket, addr), daemon=True).start()
                except OSError as e:
                    print(f"Socket error: {e}")
                    break
        finally:
            self.server_socket.close()
            print("Server has been shut down.")

#tutor's GUI class
class TutorGUI:
    def __init__(self, server):
        self.server = server
        self.root = Tkinter.Tk()
        self.root.title("Tutor Control Panel")

        self.end_button = Tkinter.Button(self.root, text="End Session", command=self.end_session)
        self.end_button.pack(pady=10)

        self.attendance_display = scrolledtext.ScrolledText(self.root, width=40, height=10)
        self.attendance_display.pack(pady=10)

        self.timer_label = Tkinter.Label(self.root, text="Session Timer: Not Started")
        self.timer_label.pack(pady=10)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    #function that ends the session upon the button being clicked
    def end_session(self):
        if self.server.session_active:
            self.server.notify_end_of_session()
            self.timer_label.config(text="Session Timer: Session has Ended")
            self.update_attendance_display()
            self.server.session_active = False

    #function that updates the session timer
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

    #function that updates the attendance displayed in the tutor's GUI
    def update_attendance_display(self):
        attendance_message = "Current Attendance:\n"
        for student_id, (student_name, port) in self.server.students.items():
            attendance_message += f"Port: {port}, ID: {student_id}, Name: {student_name}\n"

        self.attendance_display.delete(1.0, Tkinter.END)
        self.attendance_display.insert(Tkinter.END, attendance_message)

    #function that 
    def on_closing(self):
        if self.server.session_active:
            self.server.notify_end_of_session()
        self.root.destroy()

#main function
if __name__ == "__main__":
    gui = TutorGUI(None)  #creates the tutor's GUI first
    server = TutorServer(gui)  #passes the tutor's GUI to tutor server
    gui.server = server  #links back the tutor server to GUI
    threading.Thread(target=server.start, daemon=True).start()
    gui.root.mainloop()