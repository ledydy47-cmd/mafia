from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import os

app = FastAPI()

# Разрешаем запросы из Telegram
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Модели данных
class Player(BaseModel):
    name: str

class NewGame(BaseModel):
    title: str
    date: str
    max_slots: int

# База данных в памяти (пока сервер запущен, данные хранятся здесь)
db_games = [
    {
        "id": 1, 
        "title": "Пятничная Мафия", 
        "date": "15 мая, 19:00", 
        "max_slots": 10, 
        "players": ["Mr. White", "Admin"]
    }
]

# --- 1. Главная страница (отдает ваш HTML файл) ---
@app.get("/", response_class=HTMLResponse)
async def read_index():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Ошибка: Файл index.html не найден на сервере!</h1>"

# --- 2. Получение списка всех игр ---
@app.get("/games")
async def get_games():
    return db_games

# --- 3. Запись игрока на игру ---
@app.post("/register")
async def register(game_id: int, player: Player):
    for game in db_games:
        if game["id"] == game_id:
            if len(game["players"]) >= game["max_slots"]:
                raise HTTPException(status_code=400, detail="Извините, мест больше нет")
            
            # Проверка, не записан ли уже игрок с таким ником
            if player.name in game["players"]:
                raise HTTPException(status_code=400, detail="Вы уже записаны на эту игру")
                
            game["players"].append(player.name)
            return {"status": "success", "players": game["players"]}
    
    raise HTTPException(status_code=404, detail="Игра не найдена")

# --- 4. Добавление новой игры (Панель администратора) ---
@app.post("/add_game")
async def add_game(game_data: NewGame):
    new_id = len(db_games) + 1
    new_game = {
        "id": new_id,
        "title": game_data.title,
        "date": game_data.date,
        "max_slots": game_data.max_slots,
        "players": []
    }
    db_games.append(new_game)
    return {"status": "success", "game": new_game}

if __name__ == "__main__":
    import uvicorn
    # Запуск локально (для тестов на компьютере)
    uvicorn.run(app, host="0.0.0.0", port=10000)
