import time
import socket

import cv2
import datetime
import numpy
from pymongo import MongoClient

import api as face_recognition

MIN_WIDTH = 180
MIN_HEIGHT = 180

HOST = "127.0.0.1"
PORT = 5000

# TODO chequear TODOS
# TODO hacer flexible cantidad de fotos que se van a necesitar para ver bien a una persona
def main():

    # name_encodings is a dictionary with name as key and amount of encodings as value
    (known_encodings, names, name_encodings, people_collection) = init()
    server_socket = init_server()
    cap = init_camera()

    while True:
        connection, address = server_socket.accept()

        data = connection.recv(1024).decode()

        if not data:
            continue

        print("Got {}".format(data))

        if data == "Capture":

            person_encodings = []
            person_percentages = []

            t_end = time.time() + 3
            while time.time() < t_end:

                # Saco foto
                ret, frame = cap.read()
                print("Took photo")

                # Recorto frame para evitar agarrar otras personas
                height, width = frame.shape[:2]

                start_x = int(width/4)
                end_x = start_x + int(width/2)

                frame = frame[0:height, start_x:end_x]

                # Locateo
                face_locations = locate_faces(frame)

                # Encodeo cara
                faces = len(face_locations)
                if faces == 1:
                    face_encoding = face_recognition.face_encodings(frame, face_locations)[0]
                    print("Encoded face")

                elif faces == 0:
                    print("No faces detected")

                else:
                    print("Too many faces detected")

                # Guardo encoding
                person_encodings.append(face_encoding)

                # Comparo encoding y calculo top 5 porcentajes
                percentages = compare_encoding(known_encodings, face_encoding, name_encodings, names)

                # Guardo porcentajes
                person_percentages.append(percentages)

            # Hago promedio de los porcentajes (suma de % de la misma persona / cant de % de la misma persona)
            # Promedio mas alto gana
            percentage_average = {}
            for person_percentage in person_percentages:
                for key, value in person_percentage.items():

                    if key in percentage_average:
                        percentage_average[key] += value
                    else:
                        percentage_average[key] = value

            max_percentage = max(percentage_average, key=percentage_average.get)

            # Defino tolerancia
            # Segun tolerancia defino si conozco o no a esa persona
            # TODO: Adjust tolerance
            tolerance = 0.7

            # Si no conozco: recorro person_encodings y apendeo todos a known encodings, apendeando tambien el nombre a
            # names y agrego una entrada a name_encodings con el nombre y la cantidad de encodings que apendee
            # tambien guardo en la base. ver to do de init()
            if max_percentage >= tolerance:
                None
                # Persona nueva
            else:
                None
                # Conocida


def init():
    known_encodings = []
    names = []
    name_encodings = {}

    client = MongoClient()
    db = client.facer

    people_collection = db.people

    cursor = people_collection.find()
    # TODO: populate name encodings and fix the way we save people in the database
    for document in cursor:
        known_encodings.append(numpy.array(document["encoding"]))
        names.append(document["name"])

    return known_encodings, names, name_encodings, people_collection


def init_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print("Processor listening on {}:{}".format(HOST, PORT))

    return server_socket


def init_camera():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1440)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 810)
    print("Opened video capture")


def locate_faces(frame):
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

    return face_locations

    # TODO: chequear y reubicar
    # if len(face_locations) == 0:
    #     print("No faces detected")
    #     connection.send("No faces detected".encode())
    #     return
    #
    # if len(face_locations) > 1:
    #     print("Too many faces detected")
    #     connection.send("Too many faces detected".encode())
    #     return


def compare_encoding(known_encodings, face_encoding, name_encodings, names):
    percentages = {}

    matches = face_recognition.compare_faces(known_encodings, face_encoding, 0.6)

    for i, match in enumerate(matches):
        if match:
            if names[i] in percentages:
                percentages[names[i]] += 1
            else:
                percentages[names[i]] = 1

    for key, value in percentages.items():
        percentages[key] /= name_encodings[key]

    percentages = sorted(percentages, key=percentages.get, reverse=True)[:5]

    return percentages


def process_face_encoding(face_encoding, frame, face_location, known_encodings, names, people_collection, connection):
    matches = face_recognition.compare_faces(known_encodings, face_encoding, 0.6)
    known = False
    print("Compared faces")
    for i, match in enumerate(matches):
        if match:
            known = True

            print("Known face of {}".format(names[i]))
            connection.send(("Known face of {}".format(names[i])).encode())

            break

    if not known:
        print("Unknown face")

        (top, right, bottom, left) = face_location
        x = left
        y = top
        w = right - left
        h = bottom - top

        face_image = frame[y:y + h, x:x + w]

        add_visitor(face_image, names, known_encodings, face_encoding, people_collection, connection)


def add_visitor(face_image, names, known_encodings, face_encoding, people_collection, connection):
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
    connection.send(("Unknown face, added {}".format(name)).encode())


main()
