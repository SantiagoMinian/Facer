import cv2
import time


def main():

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1440)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 810)

    t_end = time.time() + 3
    while time.time() < t_end:

        ret, frame = cap.read()

        cv2.imshow("frame", frame)
        cv2.waitKey(10)


main()
