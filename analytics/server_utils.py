import os
import socket
import sys


def find_available_port(preferred_port, *, host="0.0.0.0", max_attempts=100):
    """Return preferred_port, or the next available TCP port if it is busy."""
    try:
        start_port = int(preferred_port)
    except (TypeError, ValueError):
        start_port = 0

    if start_port == 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, 0))
            return sock.getsockname()[1]

    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port

    raise RuntimeError(
        f"No available port found from {start_port} through {start_port + max_attempts - 1}."
    )


def write_port_file(port, port_file=None):
    """Write the selected port for launchers that need to open the dashboard URL."""
    port_file = port_file or os.environ.get("RIGS_DASHBOARD_PORT_FILE")
    if not port_file:
        return

    directory = os.path.dirname(os.path.abspath(port_file))
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(port_file, "w", encoding="utf-8") as handle:
        handle.write(str(port))


def run_dashboard_app(app, *, default_port, host="0.0.0.0", debug=True, port_file=None):
    """Run a Flask dashboard on an open port, falling back when the default is busy."""
    selected_port = find_available_port(default_port, host=host)
    if selected_port != int(default_port):
        print(
            f"Port {default_port} is already in use; serving dashboard on port {selected_port} instead.",
            file=sys.stderr,
            flush=True,
        )

    write_port_file(selected_port, port_file=port_file)
    print(f"Dashboard available at http://127.0.0.1:{selected_port}", flush=True)
    app.run(host=host, port=selected_port, debug=debug, use_reloader=False)
