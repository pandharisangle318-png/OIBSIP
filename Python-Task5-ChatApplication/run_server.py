"""Start ChatSphere: the web app (HTTP) and the TCP socket server (for client.py)."""

import os

from app import create_app
from chatsphere.tcp_server import start_tcp_server


def main():
    host = os.environ.get("CHATSPHERE_HOST", "127.0.0.1")
    web_port = int(os.environ.get("CHATSPHERE_PORT", "5000"))
    tcp_port = int(os.environ.get("CHATSPHERE_TCP_PORT", "5001"))

    app = create_app()
    start_tcp_server(host, tcp_port, app.config["DATABASE"], app.extensions["hub"])

    print("=" * 56)
    print("  ChatSphere is running")
    print(f"  Web app  : http://{host}:{web_port}")
    print(f"  TCP port : {host}:{tcp_port}   (python client.py)")
    print("  Press Ctrl+C to stop")
    print("=" * 56)

    # threaded=True matters: every open chat tab holds one long-lived connection.
    app.run(host=host, port=web_port, threaded=True, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
