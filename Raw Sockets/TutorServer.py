import threading #to run background tasks (not freezing tutor's GUI)
import time #for using session timers and delays
import struct #for raw packet processing
import socket #for running raw sockets
import os #replaces the import sockets to make it raw and file checks
import tkinter as Tkinter #tutor's GUI
import tkinter.scrolledtext as ScrolledText #for scrolling
from tkinter import messagebox #for dialog boxes, warnings, input

#declaration of files
ATTENDANCE_LIST_FILE = "attendance_list.txt"
SESSION_STATUS_FILE = "session_status.txt"

#tutor server class
class TutorServer:
    #function initialization for attributes and tutor's windows
    def __init__(self, gui):
        self.gui = gui
        self.students = {}  #{student_id: (student_name, port)}
        self.student_limit = 30 #max of 30 students allowed
        self.lock = threading.Lock()

        #creates the main window
        self.session_active = False
        
        #30 minutes session
        self.session_duration = 30 * 60
        self.session_end_time = None
        self.warning_sent = False

        #resets the student count file at start
        with open("student_count.txt", "w") as f:
            f.write("0")
            
        #creates a fresh start of the attendance and session file
        open(ATTENDANCE_LIST_FILE, 'w').close()
        open(SESSION_STATUS_FILE, 'w').close()

        #starts the background threading
        threading.Thread(target=self.poll_attendance_file, daemon=True).start()

    #function that adds the attendance to the attendance file
    def poll_attendance_file(self):
    
        #looks at the attendance list file for any updates
        last_lines = []
        while True:
            time.sleep(1)
            
            #reads the attendance file if it exists
            if os.path.exists(ATTENDANCE_LIST_FILE):
                with open(ATTENDANCE_LIST_FILE, "r") as f:
                    lines = f.readlines()
                    
                #if the attendance file has been updated then reloads the data into the tutor's GUI
                if lines != last_lines:
                    last_lines = lines
                    self.reload_attendance(lines)

    #reloads the attendance into the tutor's GUI with the student's port number, student id and name (internal student information)
    def reload_attendance(self, lines):
        with self.lock:
            self.students.clear()
            count = 0 #counts current students
            
            #reads each line from the file and splits the student info into port number, student id, and name
            for line in lines:
                try:
                    port, sid, name = line.strip().split('-')
                    if count < self.student_limit:
                        self.students[sid] = (name, port)
                        count += 1
                except ValueError:
                
                    #skips the extra students beyond limit
                    continue
            self.gui.update_attendance_display()
            
            #saves the current student count to a file (students will check this)
            with open("student_count.txt", "w") as count_file:
                count_file.write(str(count))

    #function to start the session and begins the threading
    def start_session(self):
        self.session_active = True
        self.session_end_time = time.time() + self.session_duration
        self.warning_sent = False

        #activates the session and monitors when it would end
        threading.Thread(target=self.session_timer, daemon=True).start()
        threading.Thread(target=self.gui.update_timer, daemon=True).start()

    #function that times the session and warns students for 5 minutes remaining
    def session_timer(self):
        while self.session_active:
            remaining = self.session_end_time - time.time()

            #when timer hits zero then ends the session
            if remaining <= 0:
                self.end_session()
                break

            #sends 5 min warning once
            if remaining <= 5 * 60 and not self.warning_sent:
                self.warning_sent = True
                self.write_session_status("WARNING_5_MINUTES")
                self.gui.show_warning_popup()

                #broadcasts the 5 minute warning message to students
                self.broadcast_raw_socket(b"popup:5min-warning")
                self.broadcast_tcp("popup:5min-warning")
                print("Sent 5-minute warning to students!")

            #real-time session timer
            minutes, seconds = divmod(int(remaining), 60)
            timer_display = f"{minutes:02}:{seconds:02}"
            self.write_session_status(f"TIMER:{timer_display}")

            #broadcasts the session timer to all students
            self.broadcast_raw_socket(f"timer:{timer_display}".encode())
            self.broadcast_tcp(f"timer:{timer_display}")
            
            #wait for a second before looping - real-time
            time.sleep(1)

    #function that ends the session and saves the attendance
    def end_session(self):
        self.session_active = False
        self.write_session_status("SESSION_ENDED")
        self.gui.timer_label.config(text="Session Timer: Ended")
        self.gui.update_attendance_display()

        #saves the final attendance
        with open("final_attendance_log.txt", "w") as f:
            for sid, (name, port) in self.students.items():
                f.write(f"Port: {port}, ID: {sid}, Name: {name}\n")

        #broadcasts the session end message
        self.broadcast_raw_socket(b"popup:session-ended")
        self.broadcast_tcp("popup:session-ended")
        print("Session ended, notified students.")

        #sends the popup message to students that the session has ended
        self.gui.show_end_popup()

    #functions that write the session status to a file
    def write_session_status(self, status_message):
        with open(SESSION_STATUS_FILE, 'w') as f:
            f.write(status_message)

    #ICMP raw broadcast (existing)
    def broadcast_raw_socket(self, payload_msg):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            icmp_type = 8
            code = 0
            checksum = 0
            packet_id = os.getpid() & 0xFFFF
            sequence = 1

            header = struct.pack('!BBHHH', icmp_type, code, checksum, packet_id, sequence)
            data = payload_msg

            checksum = self.calculate_checksum(header + data)
            header = struct.pack('!BBHHH', icmp_type, code, checksum, packet_id, sequence)
            packet = header + data

            s.sendto(packet, ('127.0.0.1', 1))
            s.close()
        except PermissionError:
            print("[Error] Run tutor script as admin/root to use raw sockets.")
        except Exception as e:
            print(f"[Raw socket error] {e}")

    #TCP broadcast
    def broadcast_tcp(self, message):
        for sid, (name, port) in self.students.items():
            try:
                student_port = int(port)
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                s.connect(('127.0.0.1', student_port))
                s.sendall(message.encode())
                s.close()
            except Exception:
                continue  #skips unreachable students

    def calculate_checksum(self, source_string):
        countTo = (int(len(source_string) / 2)) * 2
        sum = 0
        count = 0

        while count < countTo:
            thisVal = source_string[count + 1] * 256 + source_string[count]
            sum = sum + thisVal
            sum = sum & 0xffffffff
            count = count + 2

        if countTo < len(source_string):
            sum = sum + source_string[len(source_string) - 1]
            sum = sum & 0xffffffff

        sum = (sum >> 16) + (sum & 0xffff)
        sum = sum + (sum >> 16)
        answer = ~sum
        answer = answer & 0xffff
        answer = answer >> 8 | (answer << 8 & 0xff00)
        return answer

#class that holds the tutor's server GUI
class TutorGUI:
    #initialization of the tutor's GUI
    def __init__(self, server):
        self.server = server
        self.root = Tkinter.Tk()
        self.root.title("Tutor Server")

        self.attendance_display = ScrolledText.ScrolledText(self.root, width=50, height=10)
        self.attendance_display.pack(pady=10)

        self.timer_label = Tkinter.Label(self.root, text="Session Timer: Not Started")
        self.timer_label.pack(pady=10)

        self.start_button = Tkinter.Button(self.root, text="Start Session", command=self.start_session)
        self.start_button.pack(pady=5)

        self.end_button = Tkinter.Button(self.root, text="End Session", command=self.end_session)
        self.end_button.pack(pady=5)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    #function that updates the attendance
    def update_attendance_display(self):
        attendance_message = "Current Attendance:\n"
        for sid, (name, port) in self.server.students.items():
            attendance_message += f"Port: {port}, ID: {sid}, Name: {name}\n"

        #clears and displays the updated attendance list
        self.attendance_display.config(state='normal')
        self.attendance_display.delete('1.0', Tkinter.END)
        self.attendance_display.insert(Tkinter.END, attendance_message)
        self.attendance_display.config(state='disabled')

    #function that updates the session timer
    def update_timer(self):
    
        #runs the timer while the session is active
        while self.server.session_active:
            remaining_time = self.server.session_end_time - time.time()
            
            #displays the remaining time on tutor's GUI
            if remaining_time > 0:
                minutes, seconds = divmod(int(remaining_time), 60)
                self.timer_label.config(text=f"Session Timer: {minutes:02}:{seconds:02}")
                
            #when session ends, updates it on the tutor;s GUI
            else:
                self.timer_label.config(text="Session Timer: Ended")
                break
            time.sleep(1)

    #function that validates that you sent the end of session message
    def show_end_popup(self):
        messagebox.showinfo("Session Ended", "Session has ended!")

    #function that displays the warning message to tutor
    def show_warning_popup(self):
        messagebox.showinfo("5-Minute Warning", "5 minutes remaining in session!")

    #function that starts the session timer
    def start_session(self):
        if not self.server.session_active:
            self.server.start_session()

    #function that ends the session on time
    def end_session(self):
        if self.server.session_active:
            self.server.end_session()

    #function that ends the tutor's GUI when the tutor exits
    def on_closing(self):
        self.end_session()
        self.root.destroy()

#main function to run and compile the code
if __name__ == "__main__":
    gui = TutorGUI(None)
    server = TutorServer(gui)
    gui.server = server
    gui.root.mainloop()
