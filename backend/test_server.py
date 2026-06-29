#!/usr/bin/env python3
"""
Smoke-test: 3 simulated players (Alice, Bob, Charlie) run through a Mao game.
Each player takes 3 turns (playing a matching card or drawing), then disconnects.

Usage (server must already be running on :8000):
    python test_server.py
"""
from __future__ import annotations

import asyncio
import json
import urllib.request
from typing import Optional

import websockets  # bundled in venv as websockets==14.1

BASE_HTTP = "http://localhost:8000"
BASE_WS = "ws://localhost:8000"
TURNS_PER_PLAYER = 3


def http_post(path: str, body: Optional[dict] = None) -> dict:
    payload = json.dumps(body or {}).encode()
    req = urllib.request.Request(
        BASE_HTTP + path,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


async def play_as(name: str, room_code: str, chairman_token: Optional[str]) -> None:
    uri = f"{BASE_WS}/ws/{room_code}/{name}"
    if chairman_token:
        uri += f"?chairman_token={chairman_token}"
    turns = 0

    async with websockets.connect(uri) as ws:
        print(f"  [{name}] connected")

        async for raw in ws:
            msg = json.loads(raw)

            if msg["type"] == "error":
                print(f"  [{name}] ERROR  : {msg['message']}")
                continue

            if msg["type"] != "state_update":
                continue

            state = msg["state"]
            me = state["players"].get(name, {})
            current = (
                state["player_order"][state["current_turn_index"]]
                if state["player_order"]
                else "?"
            )
            print(
                f"  [{name}] game={state['state']:12s}  "
                f"top={state['top_card']}  "
                f"turn={current:8s}  "
                f"hand_size={me.get('hand_size', '?')}  "
                f"chairman={state.get('chairman_id', '?')}"
            )

            # --- chairman triggers start once all 3 players are present ---
            if state["state"] == "waiting" and state.get("chairman_id") == name:
                if len(state["player_order"]) >= 3:
                    await asyncio.sleep(0.05)
                    await ws.send(json.dumps({
                        "type": "start_game",
                        "deck_count": 1,
                    }))
                continue

            if state["state"] == "finished":
                print(f"  [{name}] game finished, leaving")
                break

            if state["state"] == "waiting":
                # non-chairman player — just wait for the chairman to start
                continue

            # --- only act on my turn ---
            if current != name:
                continue

            if turns >= TURNS_PER_PLAYER:
                print(f"  [{name}] done with {turns} turns, leaving")
                break

            turns += 1
            hand = me.get("hand", [])
            top = state["top_card"]

            # try to play a matching card, fall back to drawing
            played = False
            if top:
                for card in hand:
                    if card["rank"] == top["rank"] or card["suit"] == top["suit"]:
                        print(f"  [{name}] PLAY   : {card['rank']} of {card['suit']}")
                        await ws.send(json.dumps({"type": "play_card", "card": card}))
                        played = True
                        break

            if not played:
                print(f"  [{name}] DRAW")
                await ws.send(json.dumps({"type": "draw_card"}))

    print(f"  [{name}] disconnected (took {turns} turns)")


async def main() -> None:
    # Verify server is up
    try:
        urllib.request.urlopen(BASE_HTTP + "/health", timeout=3)
    except Exception as exc:
        raise SystemExit(f"Server not reachable at {BASE_HTTP}: {exc}")

    # Create a room with some initial rules
    resp = http_post("/rooms", {"initial_rules": ["No talking", "No drawing twice"]})
    room_code: str = resp["room_code"]
    chairman_token: str = resp["chairman_token"]
    print(f"\nRoom created  : {room_code}")
    print(f"Chairman token: {chairman_token}\n")

    # Run Alice (chairman), Bob, Charlie concurrently
    await asyncio.gather(
        play_as("Alice", room_code, chairman_token),
        play_as("Bob", room_code, None),
        play_as("Charlie", room_code, None),
    )

    print("\nAll players done.")


if __name__ == "__main__":
    asyncio.run(main())
