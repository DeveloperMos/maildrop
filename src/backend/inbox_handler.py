import json
import re
import os
import time
import threading
import config
import logging

logger = logging.getLogger("maildrop")

# Serializes read-modify-write of the inbox file (SMTP handler + cleanup thread)
_inbox_lock = threading.Lock()

# Reads the contents of the inbox.json file and returns it as a dictionary
def read_inbox() -> dict:
    try:
        with open(config.settings.INBOX_FILE_NAME, "r") as f:
            return json.load(f)
    except:
        return {}

# Writes a dictionary to the inbox.json file
# Writes to a temp file first so readers never see a half-written inbox
def write_inbox(data: dict):
    tmp_name = config.settings.INBOX_FILE_NAME + ".tmp"
    with open(tmp_name, "w") as f:
        json.dump(data, f, indent=4)
    os.replace(tmp_name, config.settings.INBOX_FILE_NAME)

# Clears inbox if it exceeds maximum
def check_inbox_size():
    if not os.path.exists(config.settings.INBOX_FILE_NAME):
        return

    if os.path.getsize(config.settings.INBOX_FILE_NAME) > config.settings.MAX_INBOX_SIZE:
        logger.warning("Inbox size limit reached, Wiping inbox.")

        write_inbox({})

# Removes emails older than MAX_EMAIL_AGE_DAYS from the inbox dict, returns how many were removed
def prune_old_emails(inbox: dict) -> int:
    cutoff = time.time() - config.settings.MAX_EMAIL_AGE_DAYS * 86400
    removed = 0

    for address in list(inbox):
        kept = [email for email in inbox[address] if email.get("Timestamp", 0) >= cutoff]
        removed += len(inbox[address]) - len(kept)

        if kept:
            inbox[address] = kept
        else:
            del inbox[address]

    return removed

# Removes old emails from the inbox file
def cleanup_inbox():
    with _inbox_lock:
        inbox = read_inbox()
        removed = prune_old_emails(inbox)

        if removed:
            write_inbox(inbox)
            logger.info(f"Removed {removed} emails older than {config.settings.MAX_EMAIL_AGE_DAYS} days.")

# Deletes every email for every address, returns how many were removed
def clear_inbox() -> int:
    with _inbox_lock:
        removed = sum(len(emails) for emails in read_inbox().values())
        write_inbox({})

    logger.warning(f"Inbox cleared on request, removed {removed} emails.")
    return removed

# Runs cleanup_inbox forever, every CLEANUP_INTERVAL seconds
def run_cleanup_loop(interval: int):
    logger.info(f"Starting inbox cleanup, removing emails older than {config.settings.MAX_EMAIL_AGE_DAYS} days every {interval}s")

    while True:
        try:
            cleanup_inbox()
        except Exception as e:
            logger.error(f"Inbox cleanup failed: {e}")

        time.sleep(interval)

# Adds a new email to the inbox
def recv_email(email_json: dict):
    recipient = email_json.get('To')

    if not recipient:
        return

    with _inbox_lock:
        check_inbox_size()
        inbox = read_inbox()
        prune_old_emails(inbox)

        if recipient not in inbox:
            inbox[recipient] = []

        logger.info(f"Inbox {email_json.get('To')} received email from {email_json.get('From')}")

        inbox[recipient].append(email_json)
        write_inbox(inbox)
