import json
import os


def load(path):
    with open(path) as f:
        cfg = json.load(f)
    cfg["port"] = int(os.environ.get("APP_PORT", cfg.get("port")))
    return cfg
