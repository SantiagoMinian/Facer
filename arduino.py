import serial
from pykeyboard import PyKeyboard

keyboard = PyKeyboard()

while True:
    ser = serial.Serial('/dev/ttyACM0')

    if ser.read() is not None:
        keyboard.press_key('x')
