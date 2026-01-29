import configparser
from pathlib import Path


_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.ini"


def ensure_config():
	cfg = configparser.ConfigParser()
	if not _CONFIG_PATH.exists():
		# create default config
		cfg["ui"] = {"log_height": "120"}
		_CONFIG_PATH.write_text("")
		with _CONFIG_PATH.open("w", encoding="utf-8") as f:
			cfg.write(f)
	return _CONFIG_PATH


def _read():
	cfg = configparser.ConfigParser()
	if _CONFIG_PATH.exists():
		cfg.read(_CONFIG_PATH, encoding="utf-8")
	return cfg


def get_int(section: str, option: str, fallback: int = 0) -> int:
	cfg = _read()
	try:
		return cfg.getint(section, option, fallback=fallback)
	except Exception:
		return int(fallback)


def set_int(section: str, option: str, value: int) -> None:
	cfg = _read()
	if section not in cfg:
		cfg[section] = {}
	cfg[section][option] = str(int(value))
	with _CONFIG_PATH.open("w", encoding="utf-8") as f:
		cfg.write(f)


def get_str(section: str, option: str, fallback: str = "") -> str:
	cfg = _read()
	try:
		return cfg.get(section, option, fallback=fallback)
	except Exception:
		return fallback


def set_str(section: str, option: str, value: str) -> None:
	cfg = _read()
	if section not in cfg:
		cfg[section] = {}
	cfg[section][option] = str(value)
	with _CONFIG_PATH.open("w", encoding="utf-8") as f:
		cfg.write(f)

