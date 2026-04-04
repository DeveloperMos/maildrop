import os
import sys
import threading
import logging

if __name__ == "__main__":
    # Check if the script is run as root
    if os.geteuid() != 0:
        print("script must be run as root")
        sys.exit(1)

    # setup logging
    from src.backend.logging import setup_logging
    setup_logging(level=logging.INFO)

    # import backend after logging is set up to report errors
    import config
    from src.backend.flask_app import run_flask_server
    from src.backend.smtp_server import run_smtp_server

    # Start the web server and SMTP server in separate threads
    flask_thread = threading.Thread(target=run_flask_server, args=(config.settings.FLASK_HOST, config.settings.FLASK_PORT))
    smtp_thread = threading.Thread(target=run_smtp_server, args=(config.settings.SMTP_HOST, config.settings.SMTP_PORT))

    flask_thread.start()
    smtp_thread.start()

    # Run forever until interrupted
    try:
        flask_thread.join()
        smtp_thread.join()
    except KeyboardInterrupt:
        print("Stopping server.")
        os._exit(0)