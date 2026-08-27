"""Starts the app on the first free port from 8000 and opens the browser."""

import socket
import sys
import threading
import webbrowser

import uvicorn


def free_port(start=8000):
    for port in range(start, start + 20):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    sys.exit("No free port between 8000 and 8019. Close another app that is "
             "serving on those ports and try again.")


def main():
    port = free_port()
    threading.Timer(1.5, webbrowser.open,
                    [f"http://127.0.0.1:{port}"]).start()
    print(f"script to vid is running at http://127.0.0.1:{port}")
    print("Leave this window open while you work. Close it to stop.")
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
