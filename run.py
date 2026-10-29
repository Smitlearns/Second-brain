"""Start the app for development: FastAPI (with Flask inside) on 8000, React on 5173.

Open http://localhost:5173. The React dev server sends /api and /flask requests on to FastAPI.
After "npm run build" in frontend/, FastAPI serves the built app on its own at http://localhost:8000.
"""
import shutil
import subprocess
import sys
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent / "frontend"
npm = shutil.which("npm")  # npm.cmd on Windows, so look it up instead of calling "npm" directly
if npm is None:
    sys.exit("npm wasn't found. Install Node.js from https://nodejs.org and try again.")

if not (FRONTEND / "node_modules").is_dir():
    subprocess.run([npm, "install"], cwd=FRONTEND, check=True)

react = subprocess.Popen([npm, "run", "dev"], cwd=FRONTEND)
try:
    subprocess.run([sys.executable, "-m", "uvicorn", "app.main:app", "--reload",
                    # Vite reloads the React code itself; watching node_modules would only slow this down
                    "--reload-exclude", "frontend", "--reload-exclude", "venv"])
except KeyboardInterrupt:
    pass  # Ctrl+C just means "stop", not an error
finally:
    if sys.platform == "win32":
        # npm starts Vite as a child process, and terminate() would leave it running
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(react.pid)], capture_output=True)
    else:
        react.terminate()
