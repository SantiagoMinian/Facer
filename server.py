import cv2
import numpy
import random
import select
import socket
import time
from pymongo import MongoClient

import api as face_recognition

MIN_WIDTH = 150
MIN_HEIGHT = 150
MIN_PHOTOS = 3

# TODO: Adjust tolerance
TOLERANCE = 0.8

HOST = "127.0.0.1"
PORT = 5000


def main():
    # name_encodings is a dictionary with name as key and amount of encodings as value
    (known_encodings, names, name_encodings, people_collection) = init()
    server_socket = init_server()
    video_capture = init_camera()
    read_list = [server_socket]

    while True:

        # Saco foto
        frame = take_photo(video_capture, False)
        if frame is None:
            continue

        readable, writable, error = select.select(read_list, [], [], 0)
        for s in readable:
            if s is server_socket:
                client_socket, address = server_socket.accept()
                read_list.append(client_socket)
                print("Connection from".format(address))
            else:
                data = s.recv(1024).decode()

                if not data:
                    continue

                print("Got {}".format(data))

                if data == "Capture":

                    person_encodings = []
                    person_percentages = []
                    person_photos = []

                    t_end = time.time() + 3
                    while time.time() < t_end:

                        # Saco foto
                        frame = take_photo(video_capture, True)
                        if frame is None:
                            continue

                        # Recorto frame para evitar agarrar otras personas
                        frame = resize_frame(frame)

                        # Locateo
                        face_locations = locate_faces(frame)

                        # Chequea cantidad de caras que se encontraron
                        check = check_locations(face_locations)

                        # Encodeo cara
                        if check:
                            face_encoding = face_recognition.face_encodings(frame, face_locations)[0]

                            (top, right, bottom, left) = face_locations[0]
                            x = left
                            y = top
                            w = right - left
                            h = bottom - top

                            person_photos.append(frame[y - 70: y + h + 50, x - 50: x + w + 50])

                            # Guardo encoding
                            person_encodings.append(face_encoding.tolist())

                            # Comparo encoding y calculo top 5 porcentajes
                            percentages = compare_encoding(known_encodings, face_encoding, name_encodings, names)

                            # Guardo porcentajes
                            person_percentages.append(percentages)

                    if len(person_photos) > MIN_PHOTOS:

                        # Hago promedio de los porcentajes, promedio mas alto gana
                        max_percentage, max_percentage_name = calculate_percentage_average(person_percentages)

                        # Segun tolerancia defino si conozco o no a esa persona
                        if max_percentage < TOLERANCE:
                            # Persona nueva
                            name = "V#{}".format(len(name_encodings) + 1)
                            for encoding in person_encodings:
                                known_encodings.append(encoding)
                                names.append(name)

                            image_path = "face{}.jpg".format(name)
                            face_image = random.choice(person_photos)

                            cv2.imwrite(image_path, face_image)

                            people_collection.insert_one(
                                {
                                    "name": name,
                                    "encodings": person_encodings,
                                    "path": image_path
                                }
                            )
                            print("Unknown face, added {}".format(name))
                            s.send(("Unknown face, added {}".format(name)).encode())
                            name_encodings[name] = len(person_encodings)
                        else:
                            # TODO: hablar con nico a ver si nos conviene agregar nuevs encodings si viene una persona conocida
                            # Conocida
                            print("Known face of {}".format(max_percentage_name))
                            s.send(("Known face of {}".format(max_percentage_name)).encode())
                    else:
                        s.send("Too many or no faces detected".encode())
                elif data == "End":
                    # TODO: make mirror return End after getting response
                    None
                    # s.close()
                    # read_list.remove(s)


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

    client = MongoClient()
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
    video_capture = cv2.VideoCapture(1)
    video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1440)
    video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 810)
    print("Opened video capture")
    return video_capture


def take_photo(video_capture, show):
    ret, frame = video_capture.read()
    if not ret:
        print("Couldn't take photo")
        return None
    if show:
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


def check_locations(face_locations):
    faces = len(face_locations)
    if faces == 1:
        print("Found 1 face")
        return True
    elif faces == 0:
        print("No faces detected")
        return False
    else:
        print("Too many faces detected")
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


def calculate_percentage_average(person_percentages):
    percentage_average = {}
    for person_percentage in person_percentages:
        for key, value in person_percentage.items():

            if key in percentage_average:
                percentage_average[key] += value
            else:
                percentage_average[key] = value
    for key, value in percentage_average.items():
        percentage_average[key] /= len(person_percentages)
    if not percentage_average:
        max_percentage = -1
        max_percentage_name = ""
    else:
        max_percentage_name = max(percentage_average, key=percentage_average.get)
        max_percentage = percentage_average[max_percentage_name]

    return max_percentage, max_percentage_name


main()
