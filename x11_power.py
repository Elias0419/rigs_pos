from ctypes import (
    Structure, CDLL, POINTER, byref,
    c_int, c_ulong, c_char_p, c_void_p, c_ushort, c_long, cast
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
libXrandr = _load("Xrandr", "libXrandr.so.2")

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
libX11.XInternAtom.argtypes   = [c_void_p, c_char_p, c_int]  # only_if_exists
libX11.XInternAtom.restype    = c_ulong

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

# DPMS extension
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


class XRRPropertyInfo(Structure):
    _fields_ = [
        ("pending",   c_int),
        ("range",     c_int),
        ("immutable", c_int),
        ("num_values", c_int),
        ("values",    POINTER(c_long)),
    ]

class XRRScreenResources(Structure):
    _fields_ = [
        ("timestamp",        c_ulong),
        ("configTimestamp",  c_ulong),
        ("ncrtc",            c_int),
        ("crtcs",            POINTER(c_ulong)),
        ("noutput",          c_int),
        ("outputs",          POINTER(c_ulong)),
        ("nmode",            c_int),
        ("modes",            c_void_p),
    ]

class XRROutputInfo(Structure):
    _fields_ = [
        ("timestamp",       c_ulong),
        ("crtc",            c_ulong),
        ("name",            c_char_p),
        ("nameLen",         c_int),
        ("mm_width",        c_ulong),
        ("mm_height",       c_ulong),
        ("connection",      c_int),
        ("subpixel_order",  c_int),
        ("ncrtc",           c_int),
        ("crtcs",           POINTER(c_ulong)),
        ("nclone",          c_int),
        ("clones",          POINTER(c_ulong)),
        ("nmode",           c_int),
        ("npreferred",      c_int),
        ("modes",           POINTER(c_ulong)),
    ]

class XRRCrtcGamma(Structure):
    _fields_ = [
        ("size",  c_int),
        ("red",   POINTER(c_ushort)),
        ("green", POINTER(c_ushort)),
        ("blue",  POINTER(c_ushort)),
    ]

libXrandr.XRRGetScreenResourcesCurrent.argtypes = [c_void_p, c_ulong]
libXrandr.XRRGetScreenResourcesCurrent.restype  = POINTER(XRRScreenResources)
libXrandr.XRRGetScreenResources.argtypes        = [c_void_p, c_ulong]
libXrandr.XRRGetScreenResources.restype         = POINTER(XRRScreenResources)
libXrandr.XRRFreeScreenResources.argtypes       = [POINTER(XRRScreenResources)]
libXrandr.XRRFreeScreenResources.restype        = None

libXrandr.XRRGetOutputPrimary.argtypes = [c_void_p, c_ulong]
libXrandr.XRRGetOutputPrimary.restype  = c_ulong
libXrandr.XRRGetOutputInfo.argtypes    = [c_void_p, POINTER(XRRScreenResources), c_ulong]
libXrandr.XRRGetOutputInfo.restype     = POINTER(XRROutputInfo)
libXrandr.XRRFreeOutputInfo.argtypes   = [POINTER(XRROutputInfo)]
libXrandr.XRRFreeOutputInfo.restype    = None

libXrandr.XRRGetCrtcGammaSize.argtypes = [c_void_p, c_ulong]
libXrandr.XRRGetCrtcGammaSize.restype  = c_int
libXrandr.XRRAllocGamma.argtypes       = [c_int]
libXrandr.XRRAllocGamma.restype        = POINTER(XRRCrtcGamma)
libXrandr.XRRSetCrtcGamma.argtypes     = [c_void_p, c_ulong, POINTER(XRRCrtcGamma)]
libXrandr.XRRSetCrtcGamma.restype      = None
libXrandr.XRRFreeGamma.argtypes        = [POINTER(XRRCrtcGamma)]
libXrandr.XRRFreeGamma.restype         = None




def _primary_crtc(dpy: c_void_p) -> c_ulong:
    root = libX11.XDefaultRootWindow(dpy)
    res = libXrandr.XRRGetScreenResourcesCurrent(dpy, root)
    if not res:
        res = libXrandr.XRRGetScreenResources(dpy, root)
    if not res:
        raise RuntimeError("XRRGetScreenResources failed")
    try:
        out = libXrandr.XRRGetOutputPrimary(dpy, root)
        if out == 0:
            raise RuntimeError("Primary RandR output not set")
        oi = libXrandr.XRRGetOutputInfo(dpy, res, out)
        if not oi:
            raise RuntimeError("XRRGetOutputInfo failed")
        try:
            crtc = oi.contents.crtc
            if crtc == 0:
                raise RuntimeError("Primary output has no active CRTC")
            return crtc
        finally:
            libXrandr.XRRFreeOutputInfo(oi)
    finally:
        libXrandr.XRRFreeScreenResources(res)

def x11_backlight_set_percent(percent):
    if not (0 <= percent <= 100):
        raise ValueError("percent must be within [0, 100]")

    dpy = _open_display()
    try:
        crtc = _primary_crtc(dpy)
        size = libXrandr.XRRGetCrtcGammaSize(dpy, crtc)
        if size <= 0:
            raise RuntimeError("XRRGetCrtcGammaSize returned non-positive size")

        gamma = libXrandr.XRRAllocGamma(size)
        if not gamma:
            raise RuntimeError("XRRAllocGamma failed")

        try:

            scale_num = percent
            scale_den = 100
            if size == 1:
                val = (65535 * scale_num) // scale_den
                gamma.contents.red[0] = gamma.contents.green[0] = gamma.contents.blue[0] = val
            else:
                top = size - 1
                for i in range(size):
                    base = (i * 65535) // top
                    val = (base * scale_num) // scale_den
                    if val < 0:
                        val = 0
                    elif val > 65535:
                        val = 65535
                    gamma.contents.red[i] = gamma.contents.green[i] = gamma.contents.blue[i] = val

            libXrandr.XRRSetCrtcGamma(dpy, crtc, gamma)
            libX11.XFlush(dpy)
        finally:
            libXrandr.XRRFreeGamma(gamma)
    finally:
        libX11.XCloseDisplay(dpy)

