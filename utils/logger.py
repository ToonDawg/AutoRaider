import logging
from pathlib import Path
from datetime import datetime

def setup_logger(log_directory: str = "logs") -> logging.Logger:
    log_dir_path = Path(log_directory)
    log_dir_path.mkdir(parents=True, exist_ok=True)

    log_file = log_dir_path / f"log_{datetime.now().strftime('%Y-%m-%d')}.log"

    logging.basicConfig(
        filename=str(log_file),
        format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S",
        encoding='utf-8',
        level=logging.DEBUG
    )
    return logging.getLogger("PyAutoRaid")