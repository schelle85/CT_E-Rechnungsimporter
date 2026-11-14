"""Capture the real Xvfb root window; never read or render a PDF file."""
import ctypes as c
import ctypes.util
import os
from pathlib import Path
import struct
import sys
import zlib

class XImage(c.Structure):
    _fields_=[("width",c.c_int),("height",c.c_int),("xoffset",c.c_int),("format",c.c_int),
              ("data",c.c_void_p),("byte_order",c.c_int),("bitmap_unit",c.c_int),
              ("bitmap_bit_order",c.c_int),("bitmap_pad",c.c_int),("depth",c.c_int),
              ("bytes_per_line",c.c_int),("bits_per_pixel",c.c_int),
              ("red_mask",c.c_ulong),("green_mask",c.c_ulong),("blue_mask",c.c_ulong)]

x=c.CDLL(ctypes.util.find_library("X11"))
x.XOpenDisplay.argtypes=[c.c_char_p];x.XOpenDisplay.restype=c.c_void_p
x.XDefaultRootWindow.argtypes=[c.c_void_p];x.XDefaultRootWindow.restype=c.c_ulong
x.XDisplayWidth.argtypes=[c.c_void_p,c.c_int];x.XDisplayWidth.restype=c.c_int
x.XDisplayHeight.argtypes=[c.c_void_p,c.c_int];x.XDisplayHeight.restype=c.c_int
x.XGetImage.argtypes=[c.c_void_p,c.c_ulong,c.c_int,c.c_int,c.c_uint,c.c_uint,c.c_ulong,c.c_int]
x.XGetImage.restype=c.POINTER(XImage)
x.XDestroyImage.argtypes=[c.POINTER(XImage)]
x.XCloseDisplay.argtypes=[c.c_void_p]
display=x.XOpenDisplay(os.environ["DISPLAY"].encode());assert display
image=None
try:
    width,height=x.XDisplayWidth(display,0),x.XDisplayHeight(display,0)
    assert 0<width<=4096 and 0<height<=4096
    image=x.XGetImage(display,x.XDefaultRootWindow(display),0,0,width,height,c.c_ulong(-1).value,2)
    assert image
    value=image.contents;assert value.bits_per_pixel in (24,32)
    raw=c.string_at(value.data,value.bytes_per_line*height);step=value.bits_per_pixel//8
    channels=[]
    for mask in (value.red_mask,value.green_mask,value.blue_mask):
        shift=(mask&-mask).bit_length()-1;channels.append((mask,shift,mask>>shift))
    pixels=bytearray()
    for row in range(height):
        pixels.append(0)
        for col in range(width):
            start=row*value.bytes_per_line+col*step
            pixel=int.from_bytes(raw[start:start+step],"little" if value.byte_order==0 else "big")
            pixels.extend(((pixel&mask)>>shift)*255//maximum for mask,shift,maximum in channels)
    def chunk(kind,data):
        return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data)&0xffffffff)
    png=b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",width,height,8,2,0,0,0))+chunk(b"IDAT",zlib.compress(pixels))+chunk(b"IEND",b"")
    Path(sys.argv[1]).write_bytes(png)
finally:
    if image:x.XDestroyImage(image)
    x.XCloseDisplay(display)
