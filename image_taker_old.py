import cv2
import socket
import pickle
import struct


HOST = "127.0.0.1"
PORT = 5000
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST, PORT))
server_socket.listen(5)
print("Image taker listining on {}:{}".format(HOST, PORT))

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1440)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 810)
print("Opened video capture")

while True:
    conn, addr = server_socket.accept()

    data = conn.recv(1024).decode()

    if not data:
        continue

    print("Got {}".format(data))

    if data == "Capture":
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        client_socket.connect(('127.0.0.1', 8088))
        print("Connected to image processor")
        
        ret, frame = cap.read()
        ret, frame = cap.read()
        ret, frame = cap.read()
        ret, frame = cap.read()
        ret, frame = cap.read()
        print("Taken photo")

        data = pickle.dumps(frame)
        client_socket.sendall(struct.pack("i", len(data)) + data)
        print("Sent photo. len: {}".format(len(data)))
        
        data = client_socket.recv(1024).decode()
        conn.sendall(data.encode())
        

conn.close()
