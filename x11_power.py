
from ctypes import (
    Structure, CDLL, POINTER, byref,
    c_int, c_ulong, c_char_p, c_void_p, c_ushort
)
from ctypes.util import find_library

def _load(name, fallback):
    path = find_library(name)
    if not path:
        path = fallback
    return CDLL(path)

libX11  = _load("X11",  "libX11.so.6")
libXss  = _load("Xss",  "libXss.so.1")
libXext = _load("Xext", "libXext.so.6")

libX11.XOpenDisplay.argtypes   = [c_char_p]
libX11.XOpenDisplay.restype    = c_void_p
libX11.XDefaultRootWindow.argtypes = [c_void_p]
libX11.XDefaultRootWindow.restype  = c_ulong
libX11.XForceScreenSaver.argtypes  = [c_void_p, c_int]  # 0 == ScreenSaverReset
libX11.XForceScreenSaver.restype   = c_int
libX11.XFlush.argtypes        = [c_void_p]
libX11.XFlush.restype         = c_int
libX11.XCloseDisplay.argtypes = [c_void_p]
libX11.XCloseDisplay.restype  = c_int
libX11.XFree.argtypes         = [c_void_p]
libX11.XFree.restype          = c_int

# XScreenSaver extension
class XScreenSaverInfo(Structure):
    _fields_ = [
        ("window", c_ulong),
        ("state", c_int),
        ("kind", c_int),
        ("til_or_since", c_ulong),
        ("idle", c_ulong),
        ("eventMask", c_ulong),
    ]

libXss.XScreenSaverQueryExtension.argtypes = [c_void_p, POINTER(c_int), POINTER(c_int)]
libXss.XScreenSaverQueryExtension.restype  = c_int
libXss.XScreenSaverAllocInfo.argtypes      = []
libXss.XScreenSaverAllocInfo.restype       = POINTER(XScreenSaverInfo)
libXss.XScreenSaverQueryInfo.argtypes      = [c_void_p, c_ulong, POINTER(XScreenSaverInfo)]
libXss.XScreenSaverQueryInfo.restype       = c_int

# Levels from <X11/extensions/dpms.h>:
DPMSModeOn      = c_ushort(0)
DPMSModeStandby = c_ushort(1)
DPMSModeSuspend = c_ushort(2)
DPMSModeOff     = c_ushort(3)

libXext.DPMSQueryExtension.argtypes = [c_void_p, POINTER(c_int), POINTER(c_int)]
libXext.DPMSQueryExtension.restype  = c_int
libXext.DPMSCapable.argtypes        = [c_void_p]
libXext.DPMSCapable.restype         = c_int
libXext.DPMSForceLevel.argtypes     = [c_void_p, c_ushort]
libXext.DPMSForceLevel.restype      = c_int

def _open_display():
    dpy = libX11.XOpenDisplay(None)
    if not dpy:
        raise RuntimeError("XOpenDisplay failed")
    return dpy

def x11_idle_ms():
    dpy = _open_display()
    try:
        ev = c_int()
        err = c_int()
        if not libXss.XScreenSaverQueryExtension(dpy, byref(ev), byref(err)):
            raise RuntimeError("XScreenSaver extension not present")
        root = libX11.XDefaultRootWindow(dpy)
        info = libXss.XScreenSaverAllocInfo()
        if not info:
            raise RuntimeError("XScreenSaverAllocInfo returned NULL")
        try:
            if not libXss.XScreenSaverQueryInfo(dpy, root, info):
                raise RuntimeError("XScreenSaverQueryInfo failed")
            return int(info.contents.idle)
        finally:
            libX11.XFree(info)
    finally:
        libX11.XCloseDisplay(dpy)

def x11_reset_idle():
    dpy = _open_display()
    try:
        libX11.XForceScreenSaver(dpy, 0)
        libX11.XFlush(dpy)
    finally:
        libX11.XCloseDisplay(dpy)

def x11_dpms_force_off():
    dpy = _open_display()
    try:
        ev = c_int()
        err = c_int()
        if not libXext.DPMSQueryExtension(dpy, byref(ev), byref(err)):
            raise RuntimeError("DPMS extension not present")
        if not libXext.DPMSCapable(dpy):
            raise RuntimeError("DPMS not capable")
        if not libXext.DPMSForceLevel(dpy, DPMSModeOff):
            raise RuntimeError("DPMSForceLevel failed")
        libX11.XFlush(dpy)
    finally:
        libX11.XCloseDisplay(dpy)
