import importlib, sys
spec = importlib.util.find_spec("numpy")
print("numpy present?", spec is not None, "->", spec.origin if spec else "")