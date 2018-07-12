# -*- coding:utf-8 -*-

"""

This file contains the Joystick class which reads joystick data under Linux.

Magic values and some functions are taken from the Unlicense'd script by rdb at:
https://gist.github.com/rdb/8864666

"""

import os
import struct
import array
from fcntl import ioctl
from glob import glob
from functools import wraps
from collections import namedtuple

def to_list(f):
     @wraps(f)
     def wrapper(*args, **kwds):
         return list(f(*args, **kwds))
     return wrapper

JoystickState = namedtuple('JoystickState', 'axis_map button_map axis_states button_states')
Event = namedtuple('Event', 'time value type number')
PollResult = namedtuple('PollResult', 'full_axis_states full_button_states event changed_axis changed_button')
ButtonChange = namedtuple('ButtonChange', 'number button value')
AxisChange = namedtuple('AxisChange', 'number axis ivalue fvalue')

class Joystick(object):
    
    @classmethod
    def available_sticks(cls):
        return glob('/dev/input/js*')
    
    def __init__(self, device_fn):
        self.dev_fn = device_fn
        self.dev = open(device_fn, 'rb')
        self.state = self.make_zero_state()
        
    def make_zero_state(self):
        
        axis_map = []
        axis_states = {}
        button_map = []
        button_states = {}
        
        state = JoystickState(axis_map=axis_map,
                              axis_states=axis_states,
                              button_map=button_map,
                              button_states=button_states)
        
        for axis_name in self.read_axis_map():
            axis_map.append(axis_name)
            axis_states[axis_name] = 0.0
        
        for button_name in self.read_button_map():
            button_map.append(button_name)
            button_states[button_name] = 0
        
        return state
        
    def read_name(self):
        """Gets the device name
        """
        buf = b'0'*64
        ioctl(self.dev, 0x80006a13 + (0x10000 * len(buf)), buf) # JSIOCGNAME(len)
        js_name = buf.decode(errors='replace')
        return js_name
    
    def read_axis_count(self):
        """Gets the number of axes
        """
        buf = array.array('B', [0])
        ioctl(self.dev, 0x80016a11, buf) # JSIOCGAXES
        num_axes = buf[0]
        return num_axes
    
    def read_button_count(self):
        """Gets the number of buttons
        """
        buf = array.array('B', [0])
        ioctl(self.dev, 0x80016a12, buf) # JSIOCGBUTTONS
        num_buttons = buf[0]
        return num_buttons
    
    @to_list
    def read_axis_map(self):
        """Gets the axis map, i.e. which axis you get when you read by index
        """
        buf = array.array('B', [0] * 0x40)
        ioctl(self.dev, 0x80406a32, buf) # JSIOCGAXMAP

        num_axes = self.read_axis_count()
        for axis in buf[:num_axes]:
            axis_name = self.AXIS_NAMES.get(axis, 'unknown(0x%02x)' % axis)
            yield axis_name            
        
    @to_list
    def read_button_map(self):
        buf = array.array('H', [0] * 200)
        ioctl(self.dev, 0x80406a34, buf) # JSIOCGBTNMAP

        num_buttons = self.read_button_count()
        for btn in buf[:num_buttons]:
            btn_name = self.BUTTON_NAMES.get(btn, 'unknown(0x%03x)' % btn)
            yield btn_name
            
    def poll(self):
        evbuf = self.dev.read(8)
        if evbuf:
            time, value, type, number = struct.unpack('IhBB', evbuf)
            event = Event(time=time, value=value, type=type, number=number)
            
            changed_axis = None
            changed_button = None

            #if type & 0x80:
            #    print("(initial)")

            if type & 0x01:
                button = self.state.button_map[number]
                if button:
                    self.state.button_states[button] = value
                    changed_button = ButtonChange(number, button, value)
                    #if value:
                    #    print("%s pressed" % (button))
                    #else:
                    #    print("%s released" % (button))

            if type & 0x02:
                axis = self.state.axis_map[number]
                if axis:
                    fvalue = value / 32767.0
                    self.state.axis_states[axis] = fvalue
                    changed_axis = AxisChange(number, axis, value, fvalue)
                    #print("%s: %.3f" % (axis, fvalue))
            
            result = PollResult(event=event,
                                full_axis_states=self.state.axis_states.copy(),
                                full_button_states = self.state.button_states.copy(),
                                changed_axis=changed_axis,
                                changed_button=changed_button)
            return result
        else:
            return None
            
        # These constants were borrowed from linux/input.h
    AXIS_NAMES = {
        0x00 : 'x',
        0x01 : 'y',
        0x02 : 'z',
        0x03 : 'rx',
        0x04 : 'ry',
        0x05 : 'rz',
        0x06 : 'trottle',
        0x07 : 'rudder',
        0x08 : 'wheel',
        0x09 : 'gas',
        0x0a : 'brake',
        0x10 : 'hat0x',
        0x11 : 'hat0y',
        0x12 : 'hat1x',
        0x13 : 'hat1y',
        0x14 : 'hat2x',
        0x15 : 'hat2y',
        0x16 : 'hat3x',
        0x17 : 'hat3y',
        0x18 : 'pressure',
        0x19 : 'distance',
        0x1a : 'tilt_x',
        0x1b : 'tilt_y',
        0x1c : 'tool_width',
        0x20 : 'volume',
        0x28 : 'misc',
    }
    
    BUTTON_NAMES = {
        0x120 : 'trigger',
        0x121 : 'thumb',
        0x122 : 'thumb2',
        0x123 : 'top',
        0x124 : 'top2',
        0x125 : 'pinkie',
        0x126 : 'base',
        0x127 : 'base2',
        0x128 : 'base3',
        0x129 : 'base4',
        0x12a : 'base5',
        0x12b : 'base6',
        0x12f : 'dead',
        0x130 : 'a',
        0x131 : 'b',
        0x132 : 'c',
        0x133 : 'x',
        0x134 : 'y',
        0x135 : 'z',
        0x136 : 'tl',
        0x137 : 'tr',
        0x138 : 'tl2',
        0x139 : 'tr2',
        0x13a : 'select',
        0x13b : 'start',
        0x13c : 'mode',
        0x13d : 'thumbl',
        0x13e : 'thumbr',

        0x220 : 'dpad_up',
        0x221 : 'dpad_down',
        0x222 : 'dpad_left',
        0x223 : 'dpad_right',

        # XBox 360 controller uses these codes.
        0x2c0 : 'dpad_left',
        0x2c1 : 'dpad_right',
        0x2c2 : 'dpad_up',
        0x2c3 : 'dpad_down',
    }
    
if __name__ == '__main__':
    js = Joystick(Joystick.available_sticks()[0])