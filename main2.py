from fastapi import FastAPI, HTTPException
import redis
import fakeredis
import json
import os
from datetime import datetime
from fastapi.responses import FileResponse

app = FastAPI()

# Connect to Redis (fallback to fakeredis if Redis not running)
try:
    r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
    r.ping()
    print("Connected to real Redis")
except Exception as e:
    print("Redis not available, using fakeredis:", e)
    r = fakeredis.FakeStrictRedis(decode_responses=True)

USER_FILE = "users.json"


# -------------------------
# Utility functions
# -------------------------
def load_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_users(users):
    with open(USER_FILE, "w") as f:
        json.dump(users, f, indent=4)


# -------------------------
# User Registration (no auth)
# -------------------------
@app.post("/register")
async def register(username: str, email: str):
    users = load_users()

    if username in users:
        raise HTTPException(status_code=400, detail="User already exists")

    users[username] = {
        "username": username,
        "email": email
    }

    save_users(users)
    return {"message": "User registered successfully"}


# -------------------------
# Submit Score (public)
# -------------------------
@app.post("/score")
async def update_score(username: str, score: float):
    if not username:
        raise HTTPException(status_code=400, detail="Username required")

    r.zadd("global_leaderboard", {username: score})

    return {
        "message": "Score updated",
        "username": username,
        "score": score
    }


# -------------------------
# Leaderboard Report JSON
# -------------------------
@app.get("/leaderboard/report")
async def generate_top_players_report(limit: int = 5):
    top_data = r.zrevrange("global_leaderboard", 0, limit - 1, withscores=True)

    report = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rankings": [
            {"rank": i + 1, "player": user, "score": score}
            for i, (user, score) in enumerate(top_data)
        ]
    }

    return report


# -------------------------
# Export Leaderboard File
# -------------------------
@app.get("/leaderboard/export")
async def export_leaderboard():
    top_data = r.zrevrange("global_leaderboard", 0, 9, withscores=True)

    file_path = "top_players_report.txt"

    with open(file_path, "w") as f:
        f.write("=== TOP PLAYERS ===\n")
        f.write(f"Generated: {datetime.now()}\n\n")
        for i, (user, score) in enumerate(top_data):
            f.write(f"{i+1}. {user} - {score} points\n")

    return FileResponse(
        path=file_path,
        filename="leaderboard_report.txt",
        media_type="text/plain"
    )


# -------------------------
# Public Leaderboard
# -------------------------
@app.get("/leaderboard/public")
async def get_public_leaderboard():
    top_10 = r.zrevrange("global_leaderboard", 0, 9, withscores=True)

    formatted = [
        {"rank": i + 1, "username": user, "score": score}
        for i, (user, score) in enumerate(top_10)
    ]

    return {
        "status": "success",
        "total_players": r.zcard("global_leaderboard"),
        "top_players": formatted
    }