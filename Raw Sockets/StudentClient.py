import threading #for polling (not freezing student's GUI)
import time #for using session timers and delays
import os #replaces the import sockets to make it raw and file checks
import socket #for running raw sockets
import struct  #for raw packet processing
import tkinter as Tkinter #students GUI
import tkinter.scrolledtext as ScrolledText #for scrolling
from tkinter import messagebox, simpledialog #for dialog boxes, warnings, input

#declaration of files
CHECK_IN_REQUESTS_FILE = "check_in_requests.txt"
ATTENDANCE_LIST_FILE = "attendance_list.txt"
SESSION_STATUS_FILE = "session_status.txt"

#student class
class StudentClient:

    #function initialization for attributes and student's windows
    def __init__(self):
        self.root = Tkinter.Tk()
        self.root.title("Student Client")

        #creates main window
        self.is_checked_in = False
        self.student_id = None
        self.student_name = None
        self.my_port = None

        #stores session data
        self.session_active = False
        self.active_ports = set()

        #tracks the session status and student's active ports
        self.create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.exit_session)

    #function for student's GUI
    def create_widgets(self):
        input_frame = Tkinter.Frame(self.root)
        input_frame.pack(pady=10)

        Tkinter.Label(input_frame, text="Student ID: *5 digits only").grid(row=0, column=0)
        self.student_id_entry = Tkinter.Entry(input_frame)
        self.student_id_entry.grid(row=0, column=1)

        Tkinter.Label(input_frame, text="First Name:").grid(row=1, column=0)
        self.first_name_entry = Tkinter.Entry(input_frame)
        self.first_name_entry.grid(row=1, column=1)

        Tkinter.Label(input_frame, text="Last Name:").grid(row=2, column=0)
        self.last_name_entry = Tkinter.Entry(input_frame)
        self.last_name_entry.grid(row=2, column=1)

        Tkinter.Label(input_frame, text="Your Port: *5 digits only").grid(row=3, column=0)
        self.port_entry = Tkinter.Entry(input_frame)
        self.port_entry.grid(row=3, column=1)

        self.check_in_button = Tkinter.Button(input_frame, text="Check In", command=self.check_in)
        self.check_in_button.grid(row=4, columnspan=2)

        self.timer_label = Tkinter.Label(self.root, text="Session Timer: Not Started")
        self.timer_label.pack(pady=5)

        Tkinter.Label(self.root, text="Attendance List:").pack()
        self.attendance_list = ScrolledText.ScrolledText(self.root, width=60, height=8, state='disabled')
        self.attendance_list.pack(pady=5)

        Tkinter.Label(self.root, text="Messages & Info:").pack()
        self.messages_box = ScrolledText.ScrolledText(self.root, width=60, height=8, state='disabled')
        self.messages_box.pack(pady=5)

        chat_frame = Tkinter.Frame(self.root)
        chat_frame.pack(pady=10)

        Tkinter.Label(chat_frame, text="Peer Port:").grid(row=0, column=0)
        self.peer_port_entry = Tkinter.Entry(chat_frame)
        self.peer_port_entry.grid(row=0, column=1)

        self.send_button = Tkinter.Button(chat_frame, text="Send Message", command=self.send_message, state='disabled')
        self.send_button.grid(row=1, columnspan=2)

        self.exit_button = Tkinter.Button(chat_frame, text="Exit Session", command=self.exit_session, state='disabled')
        self.exit_button.grid(row=2, columnspan=2)

    #function for check-in system
    def check_in(self):
    
        #checks if session is already full
        if os.path.exists("student_count.txt"):
            with open("student_count.txt", "r") as f:
                count = int(f.read().strip())
                if count >= 30:
                    messagebox.showerror("Session Full", "Session is full! Maximum 30 students allowed.")
                    return

        if self.is_checked_in:
            messagebox.showinfo("Already Checked In", "Cannot change ID/Name/Port after check-in.")
            return

        #gets the student details from the input of the student
        student_id = self.student_id_entry.get()
        first_name = self.first_name_entry.get()
        last_name = self.last_name_entry.get()
        port = self.port_entry.get()

        #validates the student id and port number as it must be unique
        if not self.validate_unique(student_id, port):
            return

        #validate student names, id, and port numbers
        if len(student_id) != 5 or not student_id.isdigit():
            messagebox.showwarning("Input Error", "Student ID must be exactly 5 digits.")
            return
        if not first_name.isalpha() or not last_name.isalpha():
            messagebox.showwarning("Input Error", "Name fields must be alphabetic.")
            return
        if len(port) != 5 or not port.isdigit():
            messagebox.showwarning("Input Error", "Port must be exactly 5 digits.")
            return

        self.student_id = student_id
        self.student_name = f"{first_name} {last_name}"
        self.my_port = port

        #writes the attendance into a txt file
        with open(ATTENDANCE_LIST_FILE, "a") as f:
            f.write(f"{port}-{student_id}-{self.student_name}\n")

        #starts background threading after students checked in successfully
        self.append_message("Checked in successfully.")
        self.is_checked_in = True
        self.session_active = True
        self.active_ports.add(port)

        #start the listeners:
        threading.Thread(target=self.poll_incoming_messages, daemon=True).start()
        threading.Thread(target=self.poll_attendance_list, daemon=True).start()
        threading.Thread(target=self.start_tcp_listener, daemon=True).start()
        threading.Thread(target=self.listen_raw_socket, daemon=True).start() #raw listener

        #disabled fields
        self.student_id_entry.config(state='disabled')
        self.first_name_entry.config(state='disabled')
        self.last_name_entry.config(state='disabled')
        self.port_entry.config(state='disabled')
        self.check_in_button.config(state='disabled')

        #enabled fields
        self.send_button.config(state='normal')
        self.exit_button.config(state='normal')

    #function for validating student id and port number (ensures no duplicates are present)
    def validate_unique(self, student_id, port):
        if os.path.exists(ATTENDANCE_LIST_FILE):
            with open(ATTENDANCE_LIST_FILE, "r") as f:
                lines = f.readlines()
                for line in lines:
                    p, sid, _ = line.strip().split('-')
                    if p == port:
                        messagebox.showerror("Error", "Port already in use!")
                        return False
                    if sid == student_id:
                        messagebox.showerror("Error", "Student ID already in use!")
                        return False
        return True

    #TCP listener from tutor
    def start_tcp_listener(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', int(self.my_port)))
        s.listen(5)
        print(f"[TCP] Listening on port {self.my_port}")

        while self.session_active:
            try:
                client_socket, addr = s.accept()
                data = client_socket.recv(1024).decode()
                client_socket.close()
                self.process_tutor_message(data)
            except Exception:
                continue

        s.close()

    #raw socket listener (ICMP)
    def listen_raw_socket(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            print("[RAW] Listening for ICMP packets...")
            while self.session_active:
                packet, addr = sock.recvfrom(65535)
                self.process_raw_packet(packet)
        except PermissionError:
            print("[Raw socket] Run as admin/root")
        except Exception as e:
            print(f"[Raw error] {e}")

    #proccesses the raw packets from the tutor using ICMP, timer, 5 minute warning and end session
    def process_raw_packet(self, packet):
        icmp_header = packet[20:28]
        icmp_type, code, checksum, p_id, sequence = struct.unpack('!BBHHH', icmp_header)

        payload = packet[28:].decode(errors='ignore')

        if payload.startswith("popup:5min-warning"):
            self.root.after(0, self.show_5min_warning)
        elif payload.startswith("popup:session-ended"):
            self.root.after(0, self.show_session_end)
        elif payload.startswith("timer:"):
            timer_value = payload.split("timer:")[1]
            self.root.after(0, lambda: self.update_timer_display(timer_value))
        elif payload.startswith("msg:"):
            message = payload.split("msg:")[1]
            self.root.after(0, lambda: self.append_message(f"Tutor: {message}"))

    #tutor messages processor
    def process_tutor_message(self, msg):
        if msg.startswith("popup:5min-warning"):
            self.root.after(0, self.show_5min_warning)
        elif msg.startswith("popup:session-ended"):
            self.root.after(0, self.show_session_end)
        elif msg.startswith("timer:"):
            timer_value = msg.split("timer:")[1]
            self.root.after(0, lambda: self.update_timer_display(timer_value))
        elif msg.startswith("msg:"):
            message = msg.split("msg:")[1]
            self.root.after(0, lambda: self.append_message(f"Tutor: {message}"))

    #displays the 5 minute warning message
    def show_5min_warning(self):
        messagebox.showwarning("5 Minute Warning", "Only 5 minutes remaining!")
        self.append_message("5 minutes remaining in session!")

    #displays the end session message
    def show_session_end(self):
        messagebox.showinfo("Session Ended", "Session has ended.")
        self.append_message("Session ended.")
        self.timer_label.config(text="Session Timer: Ended")
        self.session_active = False

    #updates the session timer on tutor's GUI
    def update_timer_display(self, timer_value):
        self.timer_label.config(text=f"Session Timer: {timer_value}")

    #function that displays the attendance list and saves it into a file
    def poll_attendance_list(self):
        while self.session_active:
            time.sleep(2)
            
            #clears the old attendance list and updates it with a new list
            if os.path.exists(ATTENDANCE_LIST_FILE):
                with open(ATTENDANCE_LIST_FILE, "r") as f:
                    lines = f.readlines()
                self.update_attendance_list(lines)

    #function that updates and displays the attendance list in student's GUI
    def update_attendance_list(self, lines):
        self.active_ports.clear()
        self.attendance_list.config(state='normal')
        self.attendance_list.delete('1.0', 'end')
        self.attendance_list.insert('end', f"{'PORT':<10} {'ID':<10} {'NAME':<30}\n")
        self.attendance_list.insert('end', "-" * 50 + "\n")

        for line in lines:
            try:
                port, sid, name = line.strip().split('-')
                self.attendance_list.insert('end', f"{port:<10} {sid:<10} {name:<30}\n")
                self.active_ports.add(port)
                
            #when the attendance is not updated and getting errors in the values being displayed to students
            except ValueError:
                continue

        self.attendance_list.config(state='disabled')
        self.attendance_list.yview('end')

    #function that sends messages to other students and validates it
    def send_message(self):
        peer_port = self.peer_port_entry.get().strip()
        
        #if port number is not in integer
        if not peer_port.isdigit():
            messagebox.showerror("Invalid Input", "Enter valid port number.")
            return
            
        #if port number you entered is your own port number
        if peer_port == self.my_port:
            messagebox.showerror("Invalid", "Cannot message yourself!")
            return
            
        #if the port is no longer available(in the session)
        if peer_port not in self.active_ports:
            messagebox.showerror("Invalid", "Port does not exist in attendance!")
            return

        #enter the message after validation of port number
        message = simpledialog.askstring("Send Message", "Enter message:")
        if not message:
            return

        #displays the message for sender
        self.append_message(f"You => {peer_port}: {message}")
        
        #displays the message to the receiver's message inbox
        peer_file = f"student_{peer_port}.txt"
        with open(peer_file, "a") as f:
            f.write(f"From {self.my_port}: {message}\n")

    #function that displays the incoming messages from other students
    def poll_incoming_messages(self):
        inbox_file = f"student_{self.my_port}.txt"
        seen_lines = set()

        #when path exists, opens the inbox file and receives new messages
        while self.session_active:
            time.sleep(1)
            if os.path.exists(inbox_file):
                with open(inbox_file, "r") as f:
                    lines = f.readlines()
                    
                #appends the messages and avoids duplicate messages
                for line in lines:
                    if line not in seen_lines:
                        seen_lines.add(line)
                        self.append_message(f"{line.strip()}")

    #function appends the message to the student's GUI message box
    def append_message(self, message):
        self.messages_box.config(state='normal')
        self.messages_box.insert('end', message + '\n')
        self.messages_box.config(state='disabled')
        self.messages_box.yview('end')

    #function that exists the session and exists the student's GUI
    def exit_session(self):
        if not self.is_checked_in:
            self.root.destroy()
            return

        #remove student from attendance file
        with open(ATTENDANCE_LIST_FILE, "r") as f:
            lines = f.readlines()
        with open(ATTENDANCE_LIST_FILE, "w") as f:
            for line in lines:
                if self.student_id not in line and self.my_port not in line:
                    f.write(line)

        #decrease the student count in student_count.txt
        if os.path.exists("student_count.txt"):
            with open("student_count.txt", "r") as f:
                count = int(f.read().strip())
            count = max(count - 1, 0) #prevent going negative
            with open("student_count.txt", "w") as f:
                f.write(str(count))

        #appends the message of the updated session
        self.append_message("Exited session. Attendance updated.")
        self.session_active = False
        self.root.destroy()

#main function to run and compile the code
if __name__ == "__main__":
    client = StudentClient()
    client.root.mainloop()
