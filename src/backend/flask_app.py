import os
import logging
from flask import Flask, url_for
from .routes import pages, api

logger = logging.getLogger("maildrop")

app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')

# static_url() adds ?v=<file mtime> so browsers and Cloudflare (which forces max-age=3600) pick up changed files right away
@app.context_processor
def static_versioning():
    def static_url(filename):
        version = int(os.path.getmtime(os.path.join(app.static_folder, filename)))
        return url_for('static', filename=filename, v=version)
    return dict(static_url=static_url)

app.register_blueprint(pages.bp) # load the blueprint for the all of the main web page routes
app.register_blueprint(api.bp) # load the blueprint for the all of the api routes

# disable flask's logging
logging.getLogger("werkzeug").setLevel(logging.ERROR)

# Runs the main flask app
def run_flask_server(host, port):
    logger.info(f"Starting Flask server on {host}:{port}")
    app.run(host=host, port=port, debug=False)