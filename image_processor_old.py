import datetime
import pickle
import socket
import struct

import cv2
import numpy
from pymongo import MongoClient

import api as face_recognition

MIN_WIDTH = 180
MIN_HEIGHT = 180

HOST = '127.0.0.1'
PORT = 8088


def main():
    known_encodings = []
    names = []

    client = MongoClient()
    db = client.facer

    people_collection = db.people

    cursor = people_collection.find()
    for document in cursor:
        known_encodings.append(numpy.array(document["encoding"]))
        names.append(document["name"])

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server_socket.bind((HOST, PORT))
    server_socket.listen(10)

    print("Image processor listening on {}:{}".format(HOST, PORT))
    while True:
        connection, address = server_socket.accept()

        print("Connected to {}".format(address))
        data = b""
        payload_size = struct.calcsize("i")
        while True:
            print("Before getting size")
            while len(data) < payload_size:
                data += connection.recv(1)
            packed_msg_size = data[:payload_size]

            data = data[payload_size:]
            msg_size = struct.unpack("i", packed_msg_size)[0]
            print("Before getting image")
            while len(data) < msg_size:
                data += connection.recv(4096)
            frame_data = data[:msg_size]
            data = data[msg_size:]

            print("Before pickle")
            frame = pickle.loads(frame_data)
            break

        print("Got photo")

        #cv2.imshow('frame', frame)
        #cv2.waitKey(10)

        locate_faces(frame, known_encodings, names, people_collection, connection)


def locate_faces(frame, known_encodings, names, people_collection, conn):
    face_locations = face_recognition.face_locations(frame)
    print("Located faces")

    small_locations = []
    for face_location in face_locations:
        (top, right, bottom, left) = face_location

        width = right - left
        height = bottom - top

        if width < MIN_WIDTH or height < MIN_HEIGHT:
            small_locations.append(face_location)

    face_locations = [location for location in face_locations if location not in small_locations]
    print("Removed small faces")

    if len(face_locations) == 0:
        print("No faces detected")
        conn.send("No faces detected".encode())
        return

    if len(face_locations) > 1:
        print("Too many faces detected")
        conn.send("Too many faces detected".encode())
        return

    face_encodings = face_recognition.face_encodings(frame, face_locations)
    print("Encoded faces")
    for i, face_encoding in enumerate(face_encodings):
        process_face_encoding(face_encoding, frame,  face_locations[i], known_encodings, names, people_collection, conn)


def process_face_encoding(face_encoding, frame,  face_location, known_encodings, names, people_collection, conn):
    matches = face_recognition.compare_faces(known_encodings, face_encoding, 0.6)
    known = False
    print("Compared faces")
    for i, match in enumerate(matches):
        if match:
            known = True

            print("Known face of {}".format(names[i]))
            conn.send(("Known face of {}".format(names[i])).encode())

            break

    if not known:
        print("Unknown face")

        (top, right, bottom, left) = face_location
        x = left
        y = top
        w = right - left
        h = bottom - top

        face_image = frame[y:y + h , x:x + w ]

        add_visitor(face_image, names, known_encodings, face_encoding, people_collection, conn)



def add_visitor(face_image, names, known_encodings, face_encoding, people_collection, conn):
    name = "V#{}".format(len(names) + 1)
    known_encodings.append(face_encoding)
    names.append(name)
    n = "face{:%Y-%m-%d%H:%M:%S}.jpg".format(datetime.datetime.now())
    cv2.imwrite(n, face_image)

    people_collection.insert_one(
        {
            "name": name,
            "encoding": face_encoding.tolist()
        }
    )

    print("Unknown face, added {}".format(name))
    conn.send(("Unknown face, added {}".format(name)).encode())


main()
