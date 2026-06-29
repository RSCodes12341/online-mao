from __future__ import annotations

import datetime
import json
import random
import secrets
import string
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from game.engine import Card, GameRoom, InvalidPlay

app = FastAPI()

import os as _os

_cors_raw = _os.environ.get("CORS_ORIGIN", "http://localhost:5173")
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# room_code -> GameRoom
rooms: Dict[str, GameRoom] = {}
# room_code -> chairman_token (only the chairman may start the game / review rules)
chairman_tokens: Dict[str, str] = {}
# room_code -> {player_id -> WebSocket}
connections: Dict[str, Dict[str, WebSocket]] = {}
# room_code -> list of rule names to apply when the chairman first connects
pending_initial_rules: Dict[str, List[str]] = {}


class CreateRoomRequest(BaseModel):
    initial_rules: List[str] = []


def _generate_room_code() -> str:
    chars = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choices(chars, k=4))
        if code not in rooms:
            return code


async def _broadcast(room_code: str) -> None:
    """Send a personalised state_update to every connected player."""
    room = rooms[room_code]
    conns = connections.get(room_code, {})
    dead: List[str] = []
    for pid, ws in list(conns.items()):
        try:
            await ws.send_json({"type": "state_update", "state": room.to_dict(pid)})
        except Exception:
            dead.append(pid)
    for pid in dead:
        conns.pop(pid, None)
        if pid in room.players:
            room.players[pid].connected = False


async def _send_error(ws: WebSocket, message: str) -> None:
    try:
        await ws.send_json({"type": "error", "message": message})
    except Exception:
        pass


async def _broadcast_chat(room_code: str, from_id: str, text: str) -> None:
    """Broadcast a chat message to every connected player in the room."""
    room = rooms[room_code]
    display_name = room.players[from_id].display_name if from_id in room.players else from_id
    payload = {
        "type": "chat_message",
        "from": display_name,
        "text": text,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }
    conns = connections.get(room_code, {})
    dead: List[str] = []
    for pid, ws in list(conns.items()):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(pid)
    for pid in dead:
        conns.pop(pid, None)
        if pid in room.players:
            room.players[pid].connected = False


# ---------------------------------------------------------------------------
# REST
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/rooms")
async def create_room(body: Optional[CreateRoomRequest] = None):
    code = _generate_room_code()
    token = secrets.token_urlsafe(16)
    rooms[code] = GameRoom(code)
    chairman_tokens[code] = token
    connections[code] = {}
    if body and body.initial_rules:
        valid = [r for r in body.initial_rules if r.strip()]
        if valid:
            pending_initial_rules[code] = valid
    return {"room_code": code, "chairman_token": token}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------


@app.websocket("/ws/{room_code}/{player_name}")
async def websocket_endpoint(
    websocket: WebSocket, room_code: str, player_name: str
) -> None:
    await websocket.accept()

    if room_code not in rooms:
        await _send_error(websocket, f"Room '{room_code}' does not exist")
        await websocket.close(code=4004)
        return

    room = rooms[room_code]
    player_id = player_name  # names are unique identifiers within a room

    # Check if this connection carries the chairman token
    chairman_token = websocket.query_params.get("chairman_token", "")
    is_claiming_chairman = (
        chairman_token
        and chairman_tokens.get(room_code) == chairman_token
        and room.chairman_id is None
    )

    def _apply_chairman(pid: str) -> None:
        room.chairman_id = pid
        if room_code in pending_initial_rules:
            room.add_initial_rules(pending_initial_rules.pop(room_code), pid)

    # Reconnect: player was already in game (e.g. brief disconnect)
    if player_id in room.players:
        room.players[player_id].connected = True
        connections[room_code][player_id] = websocket
        if is_claiming_chairman:
            _apply_chairman(player_id)
        await _broadcast(room_code)
    elif room.state != "waiting":
        await _send_error(websocket, "Game already started; new players cannot join")
        await websocket.close(code=4003)
        return
    else:
        try:
            room.add_player(player_id, player_name)
        except (InvalidPlay, ValueError) as exc:
            await _send_error(websocket, str(exc))
            await websocket.close(code=4003)
            return
        connections[room_code][player_id] = websocket
        if is_claiming_chairman:
            _apply_chairman(player_id)
        await _broadcast(room_code)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _send_error(websocket, "Invalid JSON")
                continue
            await _handle_message(room_code, player_id, websocket, msg)
    except WebSocketDisconnect:
        connections[room_code].pop(player_id, None)
        if player_id in room.players:
            room.players[player_id].connected = False
        _skip_disconnected_turns(room_code)
        await _broadcast(room_code)


def _skip_disconnected_turns(room_code: str) -> None:
    """Advance past consecutive disconnected players so the game never stalls."""
    room = rooms[room_code]
    if room.state != "in_progress" or not room.player_order:
        return
    active = connections.get(room_code, {})
    visited: set = set()
    while room.current_player_id not in active:
        pid = room.current_player_id
        if pid in visited:
            break  # all remaining players are disconnected
        visited.add(pid)
        room._advance_turn()


async def _handle_message(
    room_code: str, player_id: str, websocket: WebSocket, msg: dict
) -> None:
    room = rooms[room_code]
    msg_type = msg.get("type")

    try:
        if msg_type == "start_game":
            if room.chairman_id != player_id:
                raise InvalidPlay("Only the chairman can start the game")
            deck_count = max(1, int(msg.get("deck_count", 1)))
            room.start_game(deck_count=deck_count, hand_size=7)
            await _broadcast(room_code)

        elif msg_type == "play_card":
            raw_card = msg.get("card", {})
            card = Card(rank=raw_card["rank"], suit=raw_card["suit"])
            room.play_card(player_id, card)
            await _broadcast(room_code)

        elif msg_type == "draw_card":
            room.draw_card(player_id)
            await _broadcast(room_code)

        elif msg_type == "chat_message":
            text = str(msg.get("text", "")).strip()
            if not text:
                raise InvalidPlay("Chat message cannot be empty")
            await _broadcast_chat(room_code, player_id, text)
            return  # no state broadcast needed for chat

        elif msg_type == "propose_rule":
            name = str(msg.get("name", "")).strip()
            room.propose_rule(player_id, name)
            await _broadcast(room_code)

        elif msg_type == "review_rule":
            rule_id = str(msg.get("rule_id", ""))
            decision = str(msg.get("decision", ""))
            room.review_rule(player_id, rule_id, decision)
            await _broadcast(room_code)

        elif msg_type == "transfer_chairman":
            target_id = str(msg.get("target_player_id", ""))
            room.transfer_chairman(player_id, target_id)
            await _broadcast(room_code)

        elif msg_type == "penalize":
            target_id = str(msg.get("target_player_id", ""))
            reason = str(msg.get("reason", "")).strip()
            try:
                cards = max(1, int(msg.get("cards", 1)))
            except (ValueError, TypeError):
                cards = 1
            room.issue_penalty(player_id, target_id, reason, cards)
            await _broadcast(room_code)

        elif msg_type == "pass_turn":
            room.pass_turn(player_id)
            await _broadcast(room_code)

        elif msg_type == "timeout_turn":
            room.timeout_turn(player_id)
            await _broadcast(room_code)

        elif msg_type == "approve_win":
            room.approve_win(player_id)
            await _broadcast(room_code)

        elif msg_type == "set_countdown":
            enabled = bool(msg.get("enabled", True))
            room.set_countdown(player_id, enabled)
            await _broadcast(room_code)

        elif msg_type == "respond_penalty":
            penalty_id = str(msg.get("penalty_id", ""))
            response = str(msg.get("response", ""))
            room.respond_penalty(player_id, penalty_id, response)
            await _broadcast(room_code)

        elif msg_type == "judge_penalty":
            penalty_id = str(msg.get("penalty_id", ""))
            ruling = str(msg.get("ruling", ""))
            room.judge_penalty(player_id, penalty_id, ruling)
            await _broadcast(room_code)

        elif msg_type == "vote_penalty":
            penalty_id = str(msg.get("penalty_id", ""))
            vote = str(msg.get("vote", ""))
            room.vote_penalty(player_id, penalty_id, vote)
            await _broadcast(room_code)

        else:
            await _send_error(websocket, f"Unknown message type: '{msg_type}'")

    except (InvalidPlay, ValueError, KeyError, RuntimeError) as exc:
        await _send_error(websocket, str(exc))
