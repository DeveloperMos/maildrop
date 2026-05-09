from flask import Blueprint, render_template, request, jsonify
from .. import inbox_handler
from .. import sender
import config
import re
import random
import string
import logging
import threading

logger = logging.getLogger("maildrop")

bp = Blueprint('api', __name__)

_domain_rr_lock = threading.Lock()
_domain_rr_index = 0

def _next_domain() -> str:
    global _domain_rr_index
    domains = config.get_domains()
    with _domain_rr_lock:
        d = domains[_domain_rr_index % len(domains)]
        _domain_rr_index = (_domain_rr_index + 1) % len(domains)
    return d

# Log API requests
@bp.after_request
def log_after_request(response):
    logger.info(f"API Request | {request.remote_addr} | {request.method} | {request.path} | Status: {response.status}")
    return response

# Make a random email containing 6 characters
@bp.route('/get_random_address')
def get_random_address():
    random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return jsonify({"address": f"{random_string}@{_next_domain()}"}), 200

# Get an email domain (round-robin over configured list)
@bp.route('/get_domain')
def get_domain():
    return jsonify({"domain": _next_domain()}), 200

# This route returns the contents of an inbox
@bp.route('/get_inbox')
def get_inbox():
    addr = request.args.get("address", "").lower()
    password = request.headers.get("Authorization", None)

    if re.match(config.settings.PROTECTED_ADDRESSES, addr) and password != config.settings.PASSWORD:
        return jsonify({"error": "Unauthorized"}), 401

    inbox = inbox_handler.read_inbox()
    address_inbox = inbox.get(addr, [])
    return jsonify(address_inbox), 200

# This route sends an email
@bp.route('/send_email', methods=['POST'])
def send_email_route():
    if not config.settings.ENABLE_SENDING:
        return jsonify({"error": "Sending is disabled"}), 403
    
    data = request.json
    
    from_address = data.get('From') 
    to_address = data.get('To')
    subject = data.get('Subject')
    body = data.get('Body')

    if not all([from_address, to_address, subject, body]):
        return jsonify({"error": "Missing fields"}), 400

    domains = config.get_domains()
    if not any(from_address.lower().endswith("@" + d) for d in domains):
         return jsonify({"error": f"You can only send from one of: {', '.join(domains)}"}), 403
    
    success, message = sender.send_email(from_address, to_address, subject, body)

    if success:
        return jsonify({"message": message}), 200
    else:
        return jsonify({"error": message}), 500