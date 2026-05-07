from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Модели данных
class PlayerEntry(BaseModel):
    name: str
    nickname: Optional[str] = ""
    tg_profile: str
    user_id: int

class GameModel(BaseModel):
    id: Optional[int] = None
    title: str
    date_time: str
    master: str
    location: str
    location_url: Optional[str] = ""
    cost: str
    duration: str
    max_slots: int
    photo_url: Optional[str] = ""
    players: List[PlayerEntry] = []
    reserve: List[PlayerEntry] = []

# Временная база данных
db_games: List[GameModel] = []

@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/games")
async def get_games():
    return db_games

@app.post("/add_game")
async def add_game(game: GameModel):
    game.id = len(db_games) + 1
    db_games.append(game)
    return {"status": "success"}

@app.post("/edit_game/{game_id}")
async def edit_game(game_id: int, updated_game: GameModel):
    for i, game in enumerate(db_games):
        if game.id == game_id:
            updated_game.id = game_id
            updated_game.players = game.players # Сохраняем игроков
            updated_game.reserve = game.reserve
            db_games[i] = updated_game
            return {"status": "updated"}
    raise HTTPException(status_code=404, detail="Game not found")

@app.delete("/delete_game/{game_id}")
async def delete_game(game_id: int):
    global db_games
    db_games = [g for g in db_games if g.id != game_id]
    return {"status": "deleted"}

@app.post("/register/{game_id}")
async def register(game_id: int, p: PlayerEntry):
    for game in db_games:
        if game.id == game_id:
            # Проверка дубликатов по user_id
            all_participants = game.players + game.reserve
            if any(x.user_id == p.user_id for x in all_participants):
                raise HTTPException(status_code=400, detail="Вы уже записаны")
            
            if len(game.players) < game.max_slots:
                game.players.append(p)
                return {"status": "main_list"}
            else:
                game.reserve.append(p)
                return {"status": "reserve"}
    raise HTTPException(status_code=404, detail="Игра не найдена")

@app.post("/cancel/{game_id}")
async def cancel(game_id: int, user_id: int):
    for game in db_games:
        if game.id == game_id:
            game.players = [p for p in game.players if p.user_id != user_id]
            game.reserve = [p for p in game.reserve if p.user_id != user_id]
            # Если освободилось место, двигаем из резерва
            if len(game.players) < game.max_slots and game.reserve:
                promoted = game.reserve.pop(0)
                game.players.append(promoted)
            return {"status": "cancelled"}
    return {"status": "error"}
