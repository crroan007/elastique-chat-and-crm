
try:
    print("Attempting: import mmcv")
    import mmcv
    print(f"SUCCESS: mmcv version {mmcv.__version__}")
except ImportError as e:
    print(f"FAILURE importing mmcv: {e}")

try:
    print("Attempting: import mmpose")
    import mmpose
    print(f"SUCCESS: mmpose version {mmpose.__version__}")
except ImportError as e:
    print(f"FAILURE importing mmpose: {e}")
