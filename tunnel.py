"""Launch an ngrok tunnel to expose the local Vellore AQI Health Alert server publicly."""
from __future__ import annotations

import os
import sys
import time
from dotenv import load_dotenv
from pyngrok import conf, ngrok

# Load variables from .env
load_dotenv()

authtoken = os.getenv("NGROK_AUTHTOKEN", "").strip()
port = int(os.getenv("PORT", "8000"))

if not authtoken or authtoken == "your_ngrok_authtoken_here":
    print("\n" + "=" * 65)
    print(" NGROK AUTHTOKEN REQUIRED")
    print("=" * 65)
    print("1. Sign up / log in at: https://dashboard.ngrok.com")
    print("2. Copy your free authtoken: https://dashboard.ngrok.com/get-started/your-authtoken")
    print("3. Open your .env file and set:")
    print("   NGROK_AUTHTOKEN=your_actual_token_here")
    print("=" * 65 + "\n")
    sys.exit(1)

# Apply authtoken
conf.get_default().auth_token = authtoken

print(f"Opening ngrok tunnel to local server on port {port}...")
try:
    tunnel = ngrok.connect(port, bind_tls=True)
    public_url = tunnel.public_url

    print("\n" + "=" * 65)
    print(" VELLORE AQI ALERT - PUBLIC NGROK TUNNEL ACTIVE")
    print("=" * 65)
    print(f" Public Dashboard URL:  {public_url}")
    print(f" API Live Forecast:     {public_url}/api/v1/forecast")
    print(f" Service Health:        {public_url}/health")
    print(f" Local Target:          http://localhost:{port}")
    print("=" * 65)
    print("Tunnel is live! Share the Public Dashboard URL above.")
    print("Press Ctrl+C to stop the tunnel.\n")

    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\nClosing ngrok tunnel...")
    ngrok.kill()
    print("Tunnel closed.")
    sys.exit(0)
except Exception as exc:
    print(f"\nFailed to start ngrok tunnel: {exc}")
    sys.exit(1)
