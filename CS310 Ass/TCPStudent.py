import socket
import threading

#declares a student client
class StudentClient:
    
    #sets the port number and port address of the client
    def __init__(self, host='127.0.0.1', port=5000):
        self.server_address = (host, port)
        self.peer_port = None

    #checks the student in to the tutorial session
    def check_in(self, student_id, student_name):
        message = f"ID: {student_id}; Name: {student_name}"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect(self.server_address)
            client_socket.send(message.encode('utf-8'))
            ack = client_socket.recv(1024).decode('utf-8')
            print(ack)

        #start listening for messages from the tutor
        threading.Thread(target=self.listen_for_messages).start()

    #listens to the messages sent by the tutor
    def listen_for_messages(self):
        peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_socket.bind(('0.0.0.0', 0))  #bind to any available port
        self.peer_port = peer_socket.getsockname()[1]
        print(f"Listening for messages on port {self.peer_port}")
        peer_socket.listen(5)

        while True:
            conn, addr = peer_socket.accept()
            threading.Thread(target=self.handle_message_from_peer, args=(conn, addr)).start()

    #handles the messages from the client/student
    def handle_message_from_peer(self, conn, addr):
        print(f"Connected to peer: {addr}")
        while True:
            try:
                message = conn.recv(1024).decode('utf-8')
                if not message:
                    break
                print(f"Message from peer {addr}: {message}")  # Changed to indicate peer
            except ConnectionResetError:
                break
        conn.close()

    #starts the chat of the clients/students
    def start_chat(self):
        while True:
            peer_ip = input("Enter peer IP address (or 'exit' to quit): ")
            if peer_ip.lower() == 'exit':
                break
            try:
                peer_port = int(input("Enter peer port: "))
                message = input("Enter your message: ")
                print(f"Attempting to send message to {peer_ip}:{peer_port}")
                self.send_message_to_peer(peer_ip, peer_port, message)
            except ValueError:
                print("Invalid port number. Please enter a valid integer.")
            except Exception as e:
                print(f"Error sending message: {e}")

    #sends the message across to the other clients/students
    def send_message_to_peer(self, peer_ip, peer_port, message):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as peer_socket:
                peer_socket.connect((peer_ip, peer_port))
                peer_socket.send(message.encode('utf-8'))
                print(f"Message sent to {peer_ip}:{peer_port}")
        except socket.gaierror:
            print(f"Failed to connect to {peer_ip}:{peer_port}. Please check the IP address and port.")
        except ConnectionRefusedError:
            print(f"Connection refused by {peer_ip}:{peer_port}. Is the peer running?")
        except Exception as e:
            print(f"An error occurred while sending the message: {e}")

#main function
if __name__ == "__main__":
    student_id = input("Enter your Student ID: ")
    student_name = input("Enter your Name: ")
    client = StudentClient()
    client.check_in(student_id, student_name)
    client.start_chat()  # Start chat after checking in