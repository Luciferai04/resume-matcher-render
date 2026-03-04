import json
import socket

def get_config():
    try:
        with open("apps/backend/data/config.json", "r") as f:
            return json.load(f)
    except Exception:
        return {}

config = get_config()
provider = config.get("provider", "gemini")
model = config.get("model", "gemini-1.5-flash")
api_key = config.get("api_key", "")

# Get local IP for frontend to talk to backend if not using container names
# though in docker-compose 'backend' should work.
# But for external access it's usually localhost.

with open(".env", "w") as f:
    f.write(f"LLM_PROVIDER={provider}\n")
    f.write(f"LLM_MODEL={model}\n")
    f.write(f"LLM_API_KEY={api_key}\n")
    f.write("DB_USER=postgres\n")
    f.write("DB_PASSWORD=postgres\n")
    f.write("DB_NAME=resume_matcher\n")
    f.write("NEXT_PUBLIC_API_URL=http://localhost:8000\n")

print("Created .env file successfully")
