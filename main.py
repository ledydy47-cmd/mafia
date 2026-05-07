from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Разрешаем вашему HTML-приложению обращаться к серверу
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# Модели данных
class Player(BaseModel):
    name: str

class Game(BaseModel):
    id: int
    title: str
    date: str
    max_slots: int
    players: List[str] = []

# Имитация базы данных (в памяти)
db_games = [
    {"id": 1, "title": "Пятничная Мафия", "date": "15 мая, 19:00", "max_slots": 10, "players": ["Admin"]}
]

@app.get("/games")
async def get_games():
    return db_games

@app.post("/register")
async def register(game_id: int, player: Player):
    for game in db_games:
        if game["id"] == game_id:
            if len(game["players"]) >= game["max_slots"]:
                raise HTTPException(status_code=400, detail="Мест нет")
            game["players"].append(player.name)
            return {"status": "success", "players": game["players"]}
    raise HTTPException(status_code=404, detail="Игра не найдена")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
from fastapi.responses import HTMLResponse
import os

@app.get("/", response_class=HTMLResponse)
async def read_index():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "Файл index.html не найден на сервере"
