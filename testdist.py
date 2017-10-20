import cv2
import socket
import pickle
import struct
import api as face_recognition

MIN_WIDTH = 200
MIN_HEIGHT = 200

def main():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1440)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 810)
    print("Opened video capture")
    frames = 0
    while True:
        frames+=1
        if frames == 5:
            ret, frame = cap.read()

            locate_faces(frame)

            cv2.imshow("frame", frame)
            cv2.waitKey(10)
            frames = 0
    

def locate_faces(frame):
    face_locations = face_recognition.face_locations(frame)
    print("Located faces")

    for face_location in face_locations:
        (top, right, bottom, left) = face_location

        width = right - left
        height = bottom - top

        if width < MIN_WIDTH or height < MIN_HEIGHT:
            color =  (0,0,255)
            cv2.rectangle(frame, (left,top), (right,bottom), color, 2)
            cv2.rectangle(frame, (left,bottom-35), (right, bottom), color, cv2.FILLED)
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(frame, ("w: {} H: {}".format(width, height)),(left+6, bottom-6), font, 1.0, (255,255,255), 1)
        else:
            color =  (0,255,0)
            cv2.rectangle(frame, (left,top), (right,bottom), color, 2)
            cv2.rectangle(frame, (left,bottom-35), (right, bottom), color, cv2.FILLED)
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(frame, ("w: {} H: {}".format(width, height)),(left+6, bottom-6), font, 1.0, (255,255,255), 1)

main()
