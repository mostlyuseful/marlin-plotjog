# -*- coding:utf-8 -*-

import sys
import joystick
import serial
import threading
import numpy as np
from rx import Observable
from rx.subjects import Subject
from rx.concurrency import NewThreadScheduler

FEEDRATE = 400 # mm / minute
MAX_REACH = 0.2 # mm / feedrate
MIN_NORM = 0.2

device_fn = sys.argv[1] if len(sys.argv)>1 else joystick.Joystick.available_sticks()[0]
print("Using input device: {0}".format(device_fn))

in_stick = joystick.Joystick(device_fn)
tty = serial.Serial('/dev/ttyUSB0',250000)

def send_gcode(s):
  tty.flushInput()
  tty.write(s + b'\n')
  return tty.readline().strip()

def poll_joystick(_):
  poll_result = in_stick.poll()
  x, y = None, None
  if poll_result.changed_axis is not None:
    axis = poll_result.changed_axis
    if axis.number == 0:
        x = axis.fvalue
    elif axis.number == 1:
        y = axis.fvalue
  return x, y

def update_position(accu, update):
  return tuple( (current if current is not None else previous) for current, previous in zip(update, accu) )

joystick_positions = Observable.interval(1).map(poll_joystick).scan(update_position, (0,0))

cv = threading.Condition()
new_position = None

def new_position_available():
  global new_position
  return new_position is not None

def execute_move():
  global cv, new_position
  while True:
    with cv:
      cv.wait_for(new_position_available)
      dx, dy = new_position
      new_position = None
      
    # Relative positioning
    send_gcode(b'G91')
    # Rapid move
    send_gcode('G1 X{:.3f} Y{:.3f} F{}'.format(dx, -dy, FEEDRATE).encode('ascii'))

consumer_thread = threading.Thread(target=execute_move)
consumer_thread.daemon = True
consumer_thread.start()


def move_printer(delta):
  global cv, new_position
  if np.linalg.norm(delta) > MIN_NORM:
    dx, dy = np.array(delta) * MAX_REACH
    print(dx, dy)
    with cv:
      new_position = dx, dy
      cv.notify()

joystick_positions \
  .filter(lambda pos: all(val is not None for val in pos)) \
  .combine_latest(Observable.interval(20), lambda a,b: a) \
  .observe_on(NewThreadScheduler()) \
  .subscribe(on_next=move_printer)


input("Press any key to exit\n")

