import json, os, socket, threading, sys, math, time, urllib.parse
from dataclasses import dataclass
from typing import List, Optional, Callable
import yaml
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
gi.require_version("GstVideo", "1.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gst, Gdk, GLib

SOCK_PATH = "/tmp/camview.sock"
LATENCY_MS = 100
USE_TCP = True
FREEZE_SECS = 3.0           # restart if no buffers for this long
RESTART_MIN_GAP = 2.0       # throttle restarts
NO_CAMERA = Camera(
    name="(no cameras configured)",
    host="",
    port=0,
    username="",
    password="",
    stream="",
    params="",
    preview=False,
)

@dataclass
class Camera:
    name: str
    host: str
    port: int = 554
    username: str = "admin"
    password: str = "password"
    stream: str = "stream1"
    params: str = ""
    preview: bool = True


def load_cameras(path: str = "cameras.yaml") -> List[Camera]:
    return [
        Camera(name="Front", host="192.168.1.225", port=554,
               username="rigs_cameras", password="{nE713N?=IfA", stream="stream2"),
        Camera(name="Side", host="192.168.1.226", port=554,
               username="rigs_cameras", password="{nE713N?=IfA", stream="stream2"),
    ]

def is_no_camera(cam: Camera) -> bool:
    return cam.port == 0 or cam.host == ""

def load_cameras(path: str = "cameras.yaml") -> List[Camera]:

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        items = data["cameras"]
        if not isinstance(items, list):
            raise ValueError("'cameras' must be a list")
    except Exception as e:
        print(f"[camview] {e}", file=sys.stderr)
        return [NO_CAMERA]

    cams: List[Camera] = []
    for i, it in enumerate(items):
        try:
            cams.append(Camera(
                name=str(it["name"]),
                host=str(it["host"]),
                port=int(it.get("port", 554)),
                username=str(it.get("username", "admin")),
                password=str(it.get("password", "password")),
                stream=str(it.get("stream", "stream1")),
                params=str(it.get("params", "")),
                preview=bool(it.get("preview", True)),
            ))
        except KeyError as ke:
            print(f"[camview] camera {i}: missing required field {ke}", file=sys.stderr)
        except Exception as e:
            print(f"[camview] camera {i}: {e}", file=sys.stderr)

    return cams or [NO_CAMERA]
def _clear_container(box: Gtk.Container):
    for child in list(box.get_children()):
        box.remove(child)

def _send_cmd(cmd: dict, timeout=0.25) -> bool:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(SOCK_PATH)
            s.sendall(json.dumps(cmd).encode("utf-8"))
        return True
    except Exception:
        return False

class StreamTile(Gtk.Box):
    def __init__(self, cam: Camera, on_click: Optional[Callable[[str], None]] = None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.cam = cam
        self.on_click = on_click

        self.set_hexpand(True); self.set_vexpand(True)

        self.name_lbl = Gtk.Label(label=cam.name)
        self.name_lbl.set_halign(Gtk.Align.START)
        self.name_lbl.set_margin_start(8); self.name_lbl.set_margin_top(6)
        self.pack_start(self.name_lbl, False, False, 0)

        self.username = cam.username
        self.password = cam.password
        self.port = cam.port
        self.host = cam.host
        self.stream = cam.stream
        self.params = cam.params
        self.preview = cam.preview
        self.url = self.rtsp_url()

        # UI containers
        self._event_box = Gtk.EventBox()
        self._event_box.set_above_child(False)
        self._event_box.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self._event_box.connect("button-press-event", self._on_button_press)
        self._event_box.set_tooltip_text("Click to focus")
        self.pack_start(self._event_box, True, True, 0)

        # Pipeline state
        self.pipeline: Optional[Gst.Pipeline] = None
        self.bus = None
        self.bus_watch_active = False
        self.src = None
        self.depay = None
        self.parse = None
        self.dec = None
        self.cvt = None
        self.q = None
        self.sink = None
        self.video_widget: Optional[Gtk.Widget] = None
        self._embed_target: Gtk.Container = self._event_box  # current parent container

        # Watchdog state
        self._last_buf_t = 0.0
        self._stop_evt = threading.Event()
        self._wd_thr: Optional[threading.Thread] = None
        self._restarting = False
        self._last_restart = 0.0
        self._restart_lock = threading.Lock()

        self._create_pipeline()



    def _create_pipeline(self):
        self._destroy_pipeline()

        self.pipeline = Gst.Pipeline.new(f"pipe-{self.cam.name}")

        # Elements
        self.src = Gst.ElementFactory.make("rtspsrc", "src")
        self.depay = Gst.ElementFactory.make("rtph264depay", "depay")
        self.parse = Gst.ElementFactory.make("h264parse", "parse")
        self.dec = Gst.ElementFactory.make("avdec_h264", "dec")
        self.cvt = Gst.ElementFactory.make("videoconvert", "cvt")
        self.q = Gst.ElementFactory.make("queue", "q")
        self.sink = Gst.ElementFactory.make("gtksink", "vsink")

        if not all([self.pipeline, self.src, self.depay, self.parse, self.dec, self.cvt, self.q, self.sink]):
            raise RuntimeError("Failed to create GStreamer elements")

        # Properties
        self.src.set_property("location", self.url)
        self.src.set_property("latency", LATENCY_MS)
        self.src.set_property("do-rtsp-keep-alive", True)
        if USE_TCP:
            self.src.set_property("protocols", "tcp")
        self.sink.set_property("sync", False)

        # Add to pipeline
        for e in (self.src, self.depay, self.parse, self.dec, self.cvt, self.q, self.sink):
            self.pipeline.add(e)

        # Link static chain
        self._link_or_die(self.depay, self.parse, "depay→parse")
        self._link_or_die(self.parse, self.dec, "parse→dec")
        self._link_or_die(self.dec, self.cvt, "dec→cvt")
        self._link_or_die(self.cvt, self.q, "cvt→queue")
        self._link_or_die(self.q, self.sink, "queue→sink")

        # Dynamic link rtspsrc
        self.src.connect("pad-added", self._on_src_pad_added, self.depay)
        self.src.connect("pad-removed", self._on_src_pad_removed, self.depay)

        # Widget
        self.video_widget = self.sink.get_property("widget")
        self.video_widget.set_hexpand(True); self.video_widget.set_vexpand(True)
        self._attach_widget_to_target()

        # Bus
        self.bus = self.pipeline.get_bus()
        if self.bus and not self.bus_watch_active:
            self.bus.add_signal_watch()
            self.bus_watch_active = True
            self.bus.connect("message", self._on_bus_message)

        # Buffer probe for freeze detection
        pad = self.sink.get_static_pad("sink")
        if pad:
            pad.add_probe(Gst.PadProbeType.BUFFER, self._on_buf)

    def _link_or_die(self, a: Gst.Element, b: Gst.Element, label: str):
        if not a.link(b):
            raise RuntimeError(f"Failed to link {label}")

    def _destroy_pipeline(self):
        try:
            if self.pipeline:
                self.pipeline.set_state(Gst.State.NULL)
        except Exception:
            pass
        try:
            if self.bus and self.bus_watch_active:
                self.bus.remove_signal_watch()
        except Exception:
            pass
        self.bus_watch_active = False
        self.bus = None
        self.src = self.depay = self.parse = self.dec = self.cvt = self.q = self.sink = None
        if self.video_widget:
            parent = self.video_widget.get_parent()
            if parent:
                parent.remove(self.video_widget)
            try:
                self.video_widget.destroy()
            except Exception:
                pass
        self.video_widget = None
        self.pipeline = None

    def _on_src_pad_added(self, src, pad, depay):
        sinkpad = depay.get_static_pad("sink")
        if sinkpad and not sinkpad.is_linked():
            if pad.link(sinkpad) != Gst.PadLinkReturn.OK:
                print(f"[{self.cam.name}] pad link failed", file=sys.stderr)

    def _on_src_pad_removed(self, src, pad, depay):
        self._schedule_restart("rtsp-pad-removed")

    def _attach_widget_to_target(self):
        if not self.video_widget:
            return
        parent = self.video_widget.get_parent()
        if parent:
            parent.remove(self.video_widget)
        _clear_container(self._embed_target)
        self._embed_target.add(self.video_widget)
        self.video_widget.show_all()
        try:
            self.video_widget.queue_draw()
        except Exception:
            pass

    def _on_buf(self, pad, info):
        self._last_buf_t = time.monotonic()
        return Gst.PadProbeReturn.OK

    def _on_bus_message(self, _bus, msg):
        t = msg.type
        if t == Gst.MessageType.ERROR:
            err, dbg = msg.parse_error()
            print(f"[{self.cam.name}] ERROR: {err} {dbg}", file=sys.stderr)
            self._schedule_restart("bus-error")
        elif t == Gst.MessageType.EOS:
            print(f"[{self.cam.name}] EOS", file=sys.stderr)
            self._schedule_restart("eos")
        elif t == Gst.MessageType.ELEMENT:
            st = msg.get_structure()
            if st and st.get_name() == "GstRTSPSrcTimeout":
                print(f"[{self.cam.name}] RTSP timeout", file=sys.stderr)
                self._schedule_restart("rtsp-timeout")

    def _schedule_restart(self, reason: str):
        with self._restart_lock:
            now = time.monotonic()
            if self._restarting or (now - self._last_restart) < RESTART_MIN_GAP:
                return
            self._restarting = True
            self._last_restart = now
        print(f"[{self.cam.name}] restarting ({reason})", file=sys.stderr)
        GLib.idle_add(self._do_restart)

    def _do_restart(self):
        self._destroy_pipeline()
        self._create_pipeline()
        self._last_buf_t = time.monotonic()
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PLAYING)
        with self._restart_lock:
            self._restarting = False
        return False


    def reparent_to(self, container: Gtk.Container):
        self._embed_target = container
        self._attach_widget_to_target()
        try:
            if self.pipeline:
                self.pipeline.set_state(Gst.State.PLAYING)
        except Exception:
            pass

    def start(self):
        self._stop_evt.clear()
        self._last_buf_t = time.monotonic()
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PLAYING)
        if not self._wd_thr or not self._wd_thr.is_alive():
            self._wd_thr = threading.Thread(target=self._watchdog, daemon=True)
            self._wd_thr.start()

    def stop(self):
        self._stop_evt.set()
        try:
            if self.pipeline:
                self.pipeline.set_state(Gst.State.NULL)
        except Exception:
            pass

    def _watchdog(self):
        while not self._stop_evt.is_set():
            time.sleep(1.0)
            last = self._last_buf_t
            if last == 0.0:
                continue
            if (time.monotonic() - last) > FREEZE_SECS:
                self._schedule_restart("freeze")
                time.sleep(FREEZE_SECS)



    def _on_button_press(self, _widget, event):
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 1 and self.on_click:
            self.on_click(self.cam.name)
            return True
        return False

    def rtsp_url(self) -> str:
        user = urllib.parse.quote(self.username, safe="")
        pw = urllib.parse.quote(self.password, safe="")
        auth = f"{user}:{pw}@"
        p = f":{int(self.port)}" if self.port else ""
        q = self.params or ""
        return f"rtsp://{auth}{self.host}{p}/{self.stream}{q}"


class Viewer(Gtk.Window):
    def __init__(self, cams: List[Camera]):
        super().__init__(title="CamView")
        self.set_decorated(False)
        self.fullscreen()
        self.set_keep_above(True)
        self.connect("realize", lambda *_: self.present())
        self.set_default_size(1280, 720)
        self.connect("destroy", Gtk.main_quit)

        self.cams = cams
        self.tiles: List[StreamTile] = []
        self.focused_tile: Optional[StreamTile] = None

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.add(self.stack)

        # Grid page
        grid_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        grid_toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        grid_toolbar.set_margin_start(6); grid_toolbar.set_margin_top(6); grid_toolbar.set_margin_bottom(6)
        ret_btn_grid = Gtk.Button(label="⟵ Return to POS")
        ret_btn_grid.connect("clicked", lambda _b: Gtk.main_quit())
        grid_toolbar.pack_start(ret_btn_grid, False, False, 0)
        grid_page.pack_start(grid_toolbar, False, False, 0)

        grid_scroller = Gtk.ScrolledWindow()
        grid = Gtk.Grid(column_spacing=8, row_spacing=8, margin=8)
        grid_scroller.add(grid)
        grid_page.pack_start(grid_scroller, True, True, 0)
        self.stack.add_titled(grid_page, "grid", "Grid")

        cols = max(1, int(math.ceil(math.sqrt(len(cams)))))
        for i, cam in enumerate(cams):
            tile = StreamTile(cam, on_click=self._on_tile_clicked)
            self.tiles.append(tile)
            r, c = divmod(i, cols)
            grid.attach(tile, c, r, 1, 1)
            tile.start()

        # Detail page
        self.detail_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.stack.add_titled(self.detail_box, "detail", "Detail")

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_start(6); toolbar.set_margin_top(6); toolbar.set_margin_bottom(6)
        back_btn = Gtk.Button(label="← Back to Grid")
        back_btn.connect("clicked", lambda _b: self.show_grid())

        toolbar.pack_start(back_btn, False, False, 0)
        ret_btn_detail = Gtk.Button(label="⟵ Return to POS")
        ret_btn_detail.connect("clicked", lambda _b: Gtk.main_quit())
        toolbar.pack_start(ret_btn_detail, False, False, 0)
        self.detail_box.pack_start(toolbar, False, False, 0)

        self.detail_video = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.detail_video.set_hexpand(True); self.detail_video.set_vexpand(True)
        self.detail_box.pack_start(self.detail_video, True, True, 0)

        # IPC server
        if os.path.exists(SOCK_PATH): os.unlink(SOCK_PATH)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(SOCK_PATH)
        os.chmod(SOCK_PATH, 0o666)
        self.sock.listen(1)
        t = threading.Thread(target=self._ipc_loop, daemon=True); t.start()


    def _ipc_loop(self):
        while True:
            conn, _ = self.sock.accept()
            try:
                data = conn.recv(4096)
                msg = json.loads((data or b"{}").decode("utf-8").strip() or "{}")
                cmd = msg.get("cmd")
                if cmd == "grid":
                    GLib.idle_add(self.show_grid)
                elif cmd == "focus":
                    GLib.idle_add(self.show_focus, msg.get("name", ""))

                elif cmd == "raise":
                    GLib.idle_add(self.present_self)
                elif cmd == "quit":
                    GLib.idle_add(Gtk.main_quit)
            finally:
                conn.close()

    def _on_tile_clicked(self, name: str):
        self.show_focus(name)


    def show_grid(self):
        if self.focused_tile:
            self.focused_tile.reparent_to(self.focused_tile._event_box)
            self.focused_tile = None

        _clear_container(self.detail_video)

        for t in self.tiles:
            t.start()

        self.stack.set_visible_child_name("grid")

    def show_focus(self, name: str):
        tile = next((t for t in self.tiles if t.cam.name == name), None)
        if not tile:
            return

        if self.focused_tile and self.focused_tile is not tile:
            self.focused_tile.reparent_to(self.focused_tile._event_box)

        for t in self.tiles:
            if t is not tile:
                t.stop()

        _clear_container(self.detail_video)
        self.focused_tile = tile
        tile.reparent_to(self.detail_video)

        try:
            tile.start()
        except Exception:
            pass

        self.stack.set_visible_child_name("detail")

    def present_self(self):
        try:
            self.present()
            # Fallback for bare X (no WM): force size to monitor
            scr = self.get_screen()
            mon = scr.get_primary_monitor()
            geo = scr.get_monitor_geometry(mon)
            self.move(geo.x, geo.y)
            self.resize(geo.width, geo.height)
            self.set_keep_above(True)
        except Exception:
            pass



def main():
    Gst.init(None)

    # If another instance is up, just raise it and exit
    if _send_cmd({"cmd": "raise"}):
        return

    if os.path.exists(SOCK_PATH):
        try:  # stale socket from crashed instance
            _send_cmd({"cmd": "ping"})
        except Exception:
            try: os.unlink(SOCK_PATH)
            except Exception: pass

    cams = load_cameras()
    win = Viewer(cams)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
