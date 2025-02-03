import logging
import os
from datetime import datetime

def setup_logger(log_directory="logs"):
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)

    log_file = os.path.join(log_directory, f"log_{datetime.now().strftime('%Y-%m-%d')}.log")

    logging.basicConfig(
        filename=log_file,
        format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S",
        encoding='utf-8',
        level=logging.DEBUG
    )
    return logging.getLogger("PyAutoRaid")