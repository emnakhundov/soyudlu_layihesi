import sys

from wsgi import app

HOST = "127.0.0.1"
PORT = 8000


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "init-db":
        print("Verilənlər bazası və ilkin administrator hazırdır.")
    else:
        from waitress import serve

        print("=" * 50)
        print(f"  Sistem işə düşdü: http://{HOST}:{PORT}/login")
        print("  Dayandırmaq üçün CTRL+C basın")
        print("=" * 50)
        serve(app, host=HOST, port=PORT, threads=4)