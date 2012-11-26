#!/usr/bin/python
import argparse

from buttons import Buttons
from layout import Layout
from display import Display
from display_buffer import DisplayBuffer
from logo import logo

DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64

class Tx(object):
    def __init__(self, address, amount):
        self.address = address
        self.amount = amount

def parse_args():
    parser = argparse.ArgumentParser(description='Bitkey simulator optimized for Raspberry Pi (but works on any Linux machine).')
    parser.add_argument('-s', '--shield', dest='shield', action='store_true', help="Use RPi shield with OLED display and hardware buttons.")

    '''
    parser.add_argument('-p', '--port', dest='port', type=int, default=3333, help='Port of Stratum mining pool')
    parser.add_argument('-sh', '--stratum-host', dest='stratum_host', type=str, default='0.0.0.0', help='On which network interface listen for stratum miners. Use "localhost" for listening on internal IP only.')
    '''
     
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='Enable low-level debugging messages')
    return parser.parse_args()

def main(args):
    but = Buttons(hw=args.shield, stdin=not args.shield, pygame=not args.shield)
    buff = DisplayBuffer(DISPLAY_WIDTH, DISPLAY_HEIGHT)
    display = Display(buff, spi=args.shield, virtual=not args.shield)
    layout = Layout(buff)
    
    display.init()
    layout.show_logo(logo)
        
    while True:
        # Read button states
        button = but.read()
        if button != None:
            print "Button", button
    
        if button == True:
            #layout.show_transactions([Tx('1BRMLAB7nryYgFGrG8x9SYaokb8r2ZwAsX', 1.1), Tx('1Marek48fwU7mugmSe186do2QpUkBnpzSN', 2)], True)
            layout.show_question_dummy()
            
        if button == False:
            layout.show_logo(logo)
            
        # Handle main connection
        # TODO
        
        # Handle debug link connection
        # TODO
        
        # Display scrolling
        layout.update()
        
        # Update viewport
        display.refresh()
        

if __name__ == '__main__':
    args = parse_args()
    main(args)