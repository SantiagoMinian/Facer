import socket
import time

import cv2
import numpy
from pymongo import MongoClient

import api as face_recognition

MIN_WIDTH = 180
MIN_HEIGHT = 180

HOST = "127.0.0.1"
PORT = 5000


# TODO hacer flexible cantidad de fotos que se van a necesitar para ver bien a una persona
def main():
    # name_encodings is a dictionary with name as key and amount of encodings as value
    (known_encodings, names, name_encodings, people_collection) = init()
    server_socket = init_server()
    video_capture = init_camera()

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
                frame = take_photo(video_capture)
                if frame is None:
                    continue

                # Recorto frame para evitar agarrar otras personas
                frame = resize_frame(frame)

                # Locateo
                face_locations = locate_faces(frame)

                # Encodeo cara
                check = check_locations(face_locations, connection)

                if check:
                    face_encoding = face_recognition.face_encodings(frame, face_locations)[0]
                else:
                    # TODO: sumar uno a contador de fotos que no sirvieron
                    continue

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

            for key, value in percentage_average.items():
                percentage_average[key] /= len(person_percentages)

            max_percentage_name = max(percentage_average, key=percentage_average.get)
            max_percentage = percentage_average[max_percentage_name]

            # Defino tolerancia
            # Segun tolerancia defino si conozco o no a esa persona
            # TODO: Adjust tolerance
            tolerance = 0.7

            # Chequeo si conozco
            if max_percentage <= tolerance:
                # Persona nueva
                for encoding in person_encodings:
                    # TODO: poner bien el nombre
                    # image_name = "face{}{:%Y-%m-%d%H:%M:%S}.jpg".format(name, datetime.datetime.now())
                    # TODO: conseguir foto de la cara(una aleatoria??? o se pueden guardar todas y despues ver a mano
                    # TODO que onda, total el ganador va a ser a mano) y guardarla
                    # (top, right, bottom, left) = face_location
                    # x = left
                    # y = top
                    # w = right - left
                    # h = bottom - top
                    #
                    # face_image = frame[y:y + h, x:x + w]
                    # cv2.imwrite(image_name, face_image)

                    known_encodings.append(encoding)
                    names.append(name)

                    print("Unknown face, added {}".format(name))
                    connection.send(("Unknown face, added {}".format(name)).encode())

                name = "V#{}".format(len(name_encodings) + 1)
                person_encodings = [person_encoding.toList() for person_encoding in person_encodings]

                people_collection.insert_one(
                    {
                        "name": name,
                        "encodings": person_encodings
                        # TODO: save image path
                    }
                )
            else:
                # TODO: hablar con nico a ver si nos conviene agregar nuevs encodings si viene una persona conocida
                # Conocida
                print("Known face of {}".format(max_percentage_name))
                connection.send(("Known face of {}".format(max_percentage_name)).encode())


def resize_frame(frame):
    height, width = frame.shape[:2]
    start_x = int(width / 4)
    end_x = start_x + int(width / 2)
    frame = frame[0:height, start_x:end_x]
    return frame


def init():
    known_encodings = []
    names = []
    name_encodings = {}

    uri = "mongodb://superadmin:12345678@localhost:27017/admin?authMechanism=SCRAM-SHA-1"
    client = MongoClient(uri)
    db = client.facer

    people_collection = db.people

    cursor = people_collection.find()
    for document in cursor:
        encoding_array = numpy.array(document["encodings"])
        person_name = document["name"]

        name_encodings[person_name] = len(encoding_array)

        for face_encoding in encoding_array:
            known_encodings.append(face_encoding)
            names.append(person_name)

    return known_encodings, names, name_encodings, people_collection


def init_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print("Processor listening on {}:{}".format(HOST, PORT))

    return server_socket


def init_camera():
    video_capture = cv2.VideoCapture(0)
    video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1440)
    video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 810)
    print("Opened video capture")
    return video_capture


def take_photo(video_capture):
    ret, frame = video_capture.read()
    if not ret:
        print("Couldn't take photo")
        return None
    print("Took photo")
    return frame


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


def check_locations(face_locations, connection):
    faces = len(face_locations)
    if faces == 1:
        print("Encoded face")
        return True
    elif faces == 0:
        print("No faces detected")
        connection.send("No faces detected".encode())
        return False
    else:
        print("Too many faces detected")
        connection.send("Too many faces detected".encode())
        return False


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

    percentages = {key: percentages[key] for key in (sorted(percentages, key=percentages.get, reverse=True)[:5])}

    return percentages


main()
