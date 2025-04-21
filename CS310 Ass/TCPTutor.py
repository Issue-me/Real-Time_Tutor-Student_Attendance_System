import socket
import threading
import time
from datetime import datetime

#class declaration that uses the tutor server
class TutorServer:
    def __init__(self, host='127.0.0.1', port=5000): #function declaration for this port address and port number.
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #defining the server sockets 
        self.server_socket.bind((host, port)) #binding the host and port
        self.server_socket.listen(30)  # Max 30 students
        self.students = {} #declares students
        self.lock = threading.Lock() #locks the thread
        self.session_duration = 30 * 60  # 30 minutes in seconds
        self.session_end_time = None #session ending time

    #function declaration on handling the clients socket and port address
    def handle_client(self, client_socket, addr): 
        print(f"Connection from {addr} has been established.")
        while True: #while the connection is still connected
            try:
                message = client_socket.recv(1024).decode('utf-8') #decoding the client's socket
                if not message:
                    break
                if "has exited the session" in message:
                    self.notify_exit(message)
                else:
                    self.process_message(message, client_socket, addr)
            except ConnectionResetError: #when there is a connection error
                break
        client_socket.close() #closes the connection

    # Notify all tutors about the student's exit
    def notify_exit(self, message):
        print(message)  # Log the exit message
        self.broadcast_message(message)  # Notify all connected tutors

    #proccesses the messages (student's name and id)
    def process_message(self, message, client_socket, addr): 
        parts = message.split(';')
        student_id = parts[0]. split(':')[1].strip()
        student_name = parts[1].split(':')[1].strip()
        
        with self.lock:
            self.students[student_id] = (student_name, addr)  #store name and address
            print(f"Student checked in: {student_name} (ID: {student_id})")
            self.send_acknowledgment(client_socket) #sends acknowledgment across to the client (student)

        self.display_attendance() #displays the attendance

        #start the session timer if it's the first student checking in
        if len(self.students) == 1:
            self.session_end_time = time.time() + self.session_duration
            threading.Thread(target=self.session_timer).start()

    #sends the acknowledgement to the client/student
    def send_acknowledgment(self, client_socket):
        timestamp = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        ack_message = f"Check-in acknowledged at {timestamp}"
        client_socket.send(ack_message.encode('utf-8'))

    #displays the attendance
    def display_attendance(self):
        print("Current Attendance:")
        for student_id, (student_name, _) in self.students.items():
            print(f"ID: {student_id}, Name: {student_name}")

    #session timer of 30 minutes
    def session_timer(self):
        while time.time() < self.session_end_time:
            time.sleep(1)
        self.notify_end_of_session() #notifies the students in the session that the session has ended

    #notification for the end of session
    def notify_end_of_session(self):
        warning_time = self.session_end_time - 5 * 60  # 5 minutes before end
        while time.time() < self.session_end_time:
            if time.time() >= warning_time:
                self.broadcast_message("5 minutes left in the session!")
                break
            time.sleep(1)
        self.broadcast_message("The session has ended.")

    #sends the message across to its clients/students
    def broadcast_message(self, message):
        for student_id, (student_name, addr) in self.students.items():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as peer_socket:
                    peer_socket.connect(addr)
                    peer_socket.send(message.encode('utf-8'))
            except Exception as e:
                print(f"Failed to send message to {student_name}: {e}")

    #displays the message when the server is running
    def start(self):
        print("Tutor Server is running...")
        while True:
            client_socket, addr = self.server_socket.accept()
            threading.Thread(target=self.handle_client, args=(client_socket, addr)).start()

#main function
if __name__ == "__main__":
    server = TutorServer()
    server.start()