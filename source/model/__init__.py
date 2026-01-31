
from .storage import Storage, storage  # type: ignore

# optional global model holder for app wiring
_global_model = None

def set_global_model(m):
	global _global_model
	_global_model = m

def get_global_model():
	return _global_model

__all__ = ["Storage", "storage", "set_global_model", "get_global_model"]
