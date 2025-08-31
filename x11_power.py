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

libXrandr.XRRGetOutputPrimary.argtypes = [c_void_p, c_ulong]
libXrandr.XRRGetOutputPrimary.restype  = c_ulong

libXrandr.XRRQueryOutputProperty.argtypes = [c_void_p, c_ulong, c_ulong]
libXrandr.XRRQueryOutputProperty.restype  = POINTER(XRRPropertyInfo)

libXrandr.XRRChangeOutputProperty.argtypes = [c_void_p, c_ulong, c_ulong, c_ulong, c_int, c_int, c_void_p, c_int]
libXrandr.XRRChangeOutputProperty.restype  = None

XA_INTEGER = c_ulong(19)
PropModeReplace = c_int(0)

def _primary_output(dpy):
    root = libX11.XDefaultRootWindow(dpy)
    output = libXrandr.XRRGetOutputPrimary(dpy, root)
    if output == 0:
        raise RuntimeError("No primary RandR output")
    return output

def x11_backlight_range():

    dpy = _open_display()
    try:
        output = _primary_output(dpy)
        backlight = libX11.XInternAtom(dpy, b"Backlight", 1)  # only_if_exists=True
        if backlight == 0:
            raise RuntimeError("Backlight atom not present on primary output")
        pinfo = libXrandr.XRRQueryOutputProperty(dpy, output, backlight)
        if not pinfo:
            raise RuntimeError("XRRQueryOutputProperty failed")
        try:
            if not pinfo.contents.range or pinfo.contents.num_values < 2:
                raise RuntimeError("Backlight property is not a range")
            minv = int(pinfo.contents.values[0])
            maxv = int(pinfo.contents.values[1])
            if maxv <= minv:
                raise RuntimeError("Backlight range is invalid")
            return (minv, maxv)
        finally:
            libX11.XFree(pinfo)
    finally:
        libX11.XCloseDisplay(dpy)

def x11_backlight_set_percent(percent):
    if not (0 <= percent <= 100):
        raise ValueError("percent must be within [0, 100]")
    dpy = _open_display()
    try:
        output = _primary_output(dpy)
        backlight = libX11.XInternAtom(dpy, b"Backlight", 1)  # only_if_exists=True
        if backlight == 0:
            raise RuntimeError("Backlight atom not present on primary output")

        pinfo = libXrandr.XRRQueryOutputProperty(dpy, output, backlight)
        if not pinfo:
            raise RuntimeError("XRRQueryOutputProperty failed")
        try:
            if not pinfo.contents.range or pinfo.contents.num_values < 2:
                raise RuntimeError("Backlight property is not a range")
            minv = int(pinfo.contents.values[0])
            maxv = int(pinfo.contents.values[1])
            if maxv <= minv:
                raise RuntimeError("Backlight range is invalid")
            raw = int(round(minv + (percent / 100.0) * (maxv - minv)))
        finally:
            libX11.XFree(pinfo)

        val = c_long(raw)
        libXrandr.XRRChangeOutputProperty(
            dpy, output,
            backlight, XA_INTEGER.value,
            32, PropModeReplace.value,
            c_void_p(byref(val).value),
            1
        )
        libX11.XFlush(dpy)
    finally:
        libX11.XCloseDisplay(dpy)

#################################################
#################################################
#################################################


# Prototypes needed for property enumeration and names
libXrandr.XRRListOutputProperties.argtypes = [c_void_p, c_ulong, POINTER(c_int)]
libXrandr.XRRListOutputProperties.restype  = POINTER(c_ulong)
libXrandr.XRRFreeOutputInfo.argtypes       = [c_void_p]
libX11.XGetAtomName.argtypes               = [c_void_p, c_ulong]
libX11.XGetAtomName.restype                = c_void_p

def x11_backlight_debug_dump():

    dpy = _open_display()
    try:
        root = libX11.XDefaultRootWindow(dpy)
        output = libXrandr.XRRGetOutputPrimary(dpy, root)
        if output == 0:
            return "Primary RandR output not set."

        nprop = c_int()
        props = libXrandr.XRRListOutputProperties(dpy, output, byref(nprop))
        if not props:
            return "No RandR output properties found on primary output."

        lines = []
        try:
            lines.append(f"Primary output XID: 0x{int(output):x}")
            lines.append(f"Property count: {nprop.value}")

            backlight_atoms = []
            for i in range(nprop.value):
                atom = props[i]
                name_ptr = libX11.XGetAtomName(dpy, atom)
                try:
                    if name_ptr:
                        name = cast(name_ptr, c_char_p).value.decode("utf-8", errors="replace")
                    else:
                        name = f"ATOM_{int(atom)}"
                finally:
                    if name_ptr:
                        libX11.XFree(name_ptr)

                lines.append(f" - {name}")
                if name in ("Backlight", "BACKLIGHT"):
                    backlight_atoms.append((name, atom))

            if not backlight_atoms:
                lines.append("Backlight property not present on primary output.")
                return "\n".join(lines)

            for name, atom in backlight_atoms:
                pinfo = libXrandr.XRRQueryOutputProperty(dpy, output, atom)
                if not pinfo:
                    lines.append(f"{name}: failed to query property info.")
                    continue
                try:
                    if pinfo.contents.range and pinfo.contents.num_values >= 2:
                        minv = int(pinfo.contents.values[0])
                        maxv = int(pinfo.contents.values[1])
                        lines.append(f"{name}: range [{minv}, {maxv}]")
                    else:
                        lines.append(f"{name}: not a ranged integer property.")
                finally:
                    libX11.XFree(pinfo)

            return "\n".join(lines)

        finally:
            libX11.XFree(props)
    finally:
        libX11.XCloseDisplay(dpy)

###################################
###################################
###################################
###################################
