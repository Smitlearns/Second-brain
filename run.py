import subprocess
import sys

streamlit = subprocess.Popen(
    [sys.executable, "-m", "streamlit", "run", "streamlit_app.py",
     "--server.port", "8501",
     "--server.address", "127.0.0.1",
     "--server.headless", "true"]
)
try:
    subprocess.run([sys.executable, "-m", "uvicorn", "app.main:app", "--reload"])
except KeyboardInterrupt:
    pass  # Ctrl+C just means "stop", not an error
finally:
    streamlit.terminate()