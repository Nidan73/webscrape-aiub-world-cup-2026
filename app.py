import os
from dashboard.app import create_app

# Set up custom paths for Vercel if needed
if os.environ.get("VERCEL") == "1":
    # On Vercel, the filesystem is read-only.
    # We point the simulation directory to /tmp to prevent write crashes.
    sim_dir = "/tmp/simulations"
    os.makedirs(sim_dir, exist_ok=True)
    app = create_app(sim_dir=sim_dir)
else:
    app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
