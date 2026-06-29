# Claude Code Prompts — Online Mao

Paste these into Claude Code **in order**, one at a time, in your project folder. Let each one finish (and test it) before moving to the next. They build on each other.

---

## STAGE 1 — Core MVP

### Prompt 1.1 — Project scaffolding

```
Set up a new full-stack project called "online-mao" with this structure:

/backend  — Python, FastAPI, using WebSockets for real-time communication
/frontend — React app created with Vite

Backend:
- Use FastAPI with uvicorn.
- Add a WebSocket endpoint at /ws/{room_code}/{player_id} that just echoes any message it receives back to all connections in that room code group, so I can verify real-time multi-client communication works.
- Add a health check REST endpoint GET /health.
- Set up CORS to allow requests from the frontend's dev server.
- Use a virtual environment and a requirements.txt.

Frontend:
- React + Vite, plain CSS (no UI framework yet).
- A simple page that connects to the backend WebSocket using a room code and player name typed into a form, and shows incoming messages in a log on screen, with an input to send a test message.

Give me clear instructions for running both (backend and frontend) locally in two terminals, and confirm the round-trip works before moving on.
```

### Prompt 1.2 — Card and game-state engine (no web layer yet)

```
In /backend, create a pure-Python game engine module (no FastAPI/WebSocket code in it) for a Mao-style shedding card game. Put it in backend/game/ and write pytest unit tests for all of it in backend/tests/.

Requirements:
- Card: rank + suit, standard 52-card deck.
- Deck: builds N standard decks shuffled together (N configurable, default 1), supports dealing a hand of a given size to each player, has a draw pile and a discard pile, and automatically reshuffles the discard pile (except the top card) back into the draw pile when the draw pile is empty.
- Player: id, display name, hand (list of cards), connected flag.
- GameRoom: 
  - states: "waiting", "in_progress", "finished"
  - tracks player order, current turn index, current direction (clockwise/counterclockwise — just track as +1/-1 for now, we'll use it in stage 2), and the discard pile's top card
  - add_player(), remove_player(), start_game(deck_count, hand_size) which deals hands and flips the first card to start the discard pile
  - is_valid_play(player_id, card) -> bool: valid if the card matches the top discard card's suit OR rank
  - play_card(player_id, card) -> applies the play if valid, raises a clear exception if not, advances turn
  - draw_card(player_id) -> player draws one card from the draw pile, advances turn
  - declare_win(player_id) -> valid only if that player's hand is empty; marks game "finished"
  - a way to serialize the full room state to a plain dict (for sending over the wire later) that includes everyone's hand size but NOT the actual cards of other players (only the requesting player's own hand should ever include other players' actual cards — encode this as a to_dict(viewer_id) method)

Write thorough tests: dealing math with multiple decks, invalid plays raising/rejecting correctly, draw pile reshuffle when empty, turn order advancing correctly, win declaration validation. Run the tests and show me they pass.
```

### Prompt 1.3 — Room management + WebSocket protocol

```
Now wire the game engine from backend/game/ into the FastAPI app. Replace the echo WebSocket from before with a real protocol.

- REST: POST /rooms creates a new room, returns a short human-friendly room code (e.g. 4 uppercase letters/digits, collision-checked against active rooms) and a host token.
- WebSocket: /ws/{room_code}/{player_name} — on connect, the player is added to that room's GameRoom (create the in-memory GameRoom if it doesn't exist yet, reject the connection with a clear error if the room code doesn't exist or the game already started).
- Define a small JSON message protocol for client -> server: {"type": "start_game", "deck_count": int, "hand_size": int} (host only), {"type": "play_card", "card": {...}}, {"type": "draw_card"}, {"type": "declare_win"}.
- Server -> client: after every state-changing action, broadcast {"type": "state_update", "state": <to_dict(viewer_id) for this viewer>} to every connected player in that room (each gets their own view with only their own hand visible). Also send {"type": "error", "message": "..."} back to a single client if their action was invalid, without affecting others.
- Handle disconnects gracefully: mark the player as disconnected in the room state, don't crash the game, broadcast the updated state to everyone else.

Keep all game logic in the existing game engine module — this prompt should only add the FastAPI room/connection management and message routing around it. Test manually with multiple WebSocket clients (or a quick script) and show me it works for at least 3 simulated players.
```

### Prompt 1.4 — Basic playable frontend

```
Build out the React frontend into a minimally playable game UI. Replace the test page from prompt 1.1.

Screens/flow:
1. Landing: "Create Room" (enter your name, choose deck count and starting hand size) or "Join Room" (enter your name + room code).
2. Lobby: shows room code prominently (easy to copy/share), list of joined players, and a "Start Game" button visible only to the host. Waits here until the host starts.
3. Table view, once the game starts:
   - Your hand as a row of clickable cards (rank + suit, readable at a glance — text-based cards are fine for now, no need for card images yet)
   - The current top discard card, clearly shown
   - Other players shown around the table with just their name and card count (not their actual cards)
   - Whose turn it is, highlighted clearly
   - A "Draw" button (enabled only on your turn)
   - A "Declare Mao" button (enabled only when your hand is empty)
   - Clicking one of your cards attempts to play it; show a clear inline error if the server rejects it (e.g. "doesn't match the top card") without crashing or losing your turn state

Keep styling minimal but clean — this is a functional pass, not the final visual polish (that's stage 2). Connect everything to the backend's WebSocket protocol from prompt 1.3. Walk me through testing a full game end to end with at least 2 browser windows.
```

### Prompt 1.5 — Patch: auto-win, fixed hand size, basic chat

```
Make three changes to the existing app:

1. Remove the "Declare Mao" button entirely. Instead, the game should detect a win automatically: as soon as a player's play_card action leaves their hand empty, the backend should immediately mark the game "finished" with that player as the winner, and broadcast that result to everyone — no manual declaration step needed.

2. Remove the starting hand size choice from the "Create Room" screen. Use a fixed default hand size (7 cards) for every game — don't expose it as a setting anywhere in the UI or room-creation payload. Deck count stays configurable as before.

3. Add a basic chat feature, separate from game actions:
   - Backend: new WebSocket message type {"type": "chat_message", "text": str} from a client; broadcast it to everyone in the room as {"type": "chat_message", "from": player_name, "text": str, "timestamp": ...}. No persistence needed beyond the room's lifetime — just relay it. Reject empty messages.
   - Frontend: a simple chat panel visible during both the lobby and the table view (so people can talk before and during the game) — scrollable message list, text input, send button/Enter-to-send.

Update or remove any existing tests/UI tied to the old Declare Mao button or the hand-size selector so nothing references them anymore. Walk me through testing all three changes with at least 2 browser windows.
```

---

## STAGE 2 — Chairman, rules, penalties/challenges, and polish

Terminology note for all prompts below: the room's lead player is called the **Chairman**, not "host." The chairman can hand the role to any other connected player at any time.

### Prompt 2.1 — Chairman role and the rule system

```
Rework the existing "host" concept into a "Chairman" role and add a rule system on top of the existing engine and protocol.

Backend:
- Rename host/host_token concepts to "chairman" throughout (room creator starts as chairman).
- New action {"type": "transfer_chairman", "target_player_id": str} — only the current chairman can call this; it immediately hands chairman status to the target player (who must be connected and in the room).
- Rule: {id, name: str, status: "active" | "pending_approval", proposed_by, timestamp}. A rule is just a short name — no description field.
- When creating a room, the chairman can submit an initial list of rule names; these are created with status "active" immediately (no approval needed since the chairman set them).
- While a room is in "waiting" (lobby) state, any player can propose a new rule: {"type": "propose_rule", "name": str} — creates a Rule with status "pending_approval".
- The chairman can act on a pending proposal: {"type": "review_rule", "rule_id": str, "decision": "approve" | "reject"} (chairman only). Approved rules become "active"; rejected ones are removed (keep a short log entry that it was rejected, for transparency).
- Include the full rule list (with status) and the current chairman_id in the broadcast room state.

Frontend:
- Create Room screen: chairman can type and add one or more rule names before starting (simple repeatable "add rule" input, removable before submit).
- Lobby screen: a "Rules" panel showing active rules, plus a section for pending proposals. Any player can type a rule name and submit a proposal. The chairman sees Approve/Reject buttons next to each pending proposal; other players just see "pending chairman approval."
- Somewhere visible (e.g. player list), let the chairman transfer their role to another player via a button next to that player's name; everyone's UI should immediately reflect the new chairman.

Test: room creation with initial rules, a non-chairman proposing a rule, chairman approving and rejecting proposals, and chairman transfer updating everyone's view live.
```

### Prompt 2.2 — Penalty, accept/reject, and challenge resolution

```
Add the penalty system. The card comes first, the citation comes second: issuing a penalty immediately gives the target the card(s), and the act of issuing it is also where the penalizer cites which active rule was broken. There's no "pending, waiting for cards" step — the card is already given by the time anyone can challenge it.

Backend, extend the game engine + protocol (cover with tests):
- New action {"type": "penalize", "target_player_id": str, "rule_id": str, "cards": int = 1} — any connected player (not just the chairman) can penalize any other player at any time, citing one active rule. Reject if rule_id isn't an active rule, or if target == self.
- On this action: immediately add `cards` to the target's hand from the draw pile, and create a Penalty record: {id, from_player, to_player, rule_id, cards, status: "issued", created_at}. Broadcast it to the room, and make sure the target gets a clear actionable prompt that a penalty (already applied) is awaiting their response.
- Target's action: {"type": "respond_penalty", "penalty_id": str, "response": "accept" | "reject"}.
  - "accept": no card change (the card was already given) — just mark status "accepted" and log it.
  - "reject": status -> "under_review", and route to a judge:
    - If the chairman is NOT the one who issued the penalty (from_player != chairman_id): the chairman gets a judge prompt: {"type": "judge_penalty", "penalty_id": str, "ruling": "uphold" | "overturn"} (chairman only).
    - If the chairman IS the one who issued the penalty (from_player == chairman_id): instead open a popular vote among all other connected players (everyone except from_player and to_player): broadcast {"type": "penalty_vote_started", "penalty_id"}, accept {"type": "vote_penalty", "penalty_id", "vote": "uphold" | "overturn"} from each eligible voter, and once all eligible voters have voted, tally a simple majority. Treat a tie as "uphold" (default — flag this to me, it's adjustable).
- Resolution outcomes:
  - Upheld (the challenge failed — target was correctly penalized and wrongly refuted it): target keeps the cards they already received, PLUS gets 1 extra card for failing to accept a valid penalty. Status -> "upheld". Log both parts clearly.
  - Overturned (the challenge succeeded — the original penalty was wrong): reverse it — remove the originally-given `cards` from the target's hand (back to the discard or draw pile, your call, just don't duplicate cards), and give the penalizer (from_player) 1 "faulty penalty" card instead. Status -> "overturned". Log it as a faulty penalty against the penalizer.
  - Edge case: if the target already played one of the penalty cards before the challenge was resolved and an "overturned" reversal can't remove the exact card(s), fall back to just removing however many of their current cards are available to remove (down to a minimum of 0) — note this clearly in the log rather than erroring out.
- Maintain a running log of penalties (full lifecycle: issued-with-cards-applied → accepted/rejected → resolved) in the broadcast state, last ~50 entries is fine.

Frontend:
- "Penalize" button always visible during a game: pick a target player, an active rule, and a card count (default 1, editable), then submit — this immediately gives the card(s) and shows the citation together as one action, there's no separate "give card" and "cite rule" step from the UI's perspective even though card application happens first internally.
- When you're the target of a penalty that just hit your hand, you get a clear modal/banner showing what rule was cited, with "Accept Penalty" / "Reject Penalty" buttons.
- When a challenge needs the chairman's ruling, the chairman gets an "Uphold" / "Overturn" prompt. When it needs a popular vote instead, every eligible voter gets a simple uphold/overturn vote UI, and everyone can see the live tally as votes come in.
- Game log panel shows the full lifecycle of each penalty (cards given + rule cited, accepted/rejected, who judged or how the vote went, final outcome including any reversal).

Test the full happy path (accept), and both challenge paths (chairman judge, and popular vote when chairman is the penalizer), confirming cards are applied at issuance and correctly reversed/added on overturn or upheld.
```

### Prompt 2.3 — Win flow: winner adds a rule, then a new round

```
Change what happens when a player empties their hand (currently auto-detected as a win from the Stage 1 patch).

Backend:
- On win, instead of just marking the room "finished," transition to a new state "round_over" and record the winner. Don't reset anything yet.
- Give the winner one action: {"type": "add_winner_rule", "name": str} — creates a new Rule with status "active" immediately (no chairman approval needed — this one is the winner's privilege). Only the recorded winner of this round can call it, and only once per round.
- After the winner submits their rule (or explicitly skips, add a {"type": "skip_winner_rule"} action too), transition the room back to "waiting" (lobby): same players, same connections, same accumulated active rule list (including the new one), hands/piles cleared. The chairman then starts the next round the normal way ({"type": "start_game", ...}) which deals fresh hands to the same player list.
- The room's active rule list and penalty log persist and keep growing across rounds within the same room — only hands/piles/turn state reset between rounds.

Frontend:
- "round_over" screen: announce the winner clearly, show the winner a one-field form ("Name your rule") with a submit and a skip option; everyone else sees "waiting for <winner> to add a rule" with the current rule list visible.
- After the winner acts, transition everyone back to the lobby view (same as Stage 1's lobby, now also showing the accumulated rules panel from Prompt 2.1) until the chairman starts the next round.

Test a full cycle: play a round to completion, winner adds a rule, confirm it shows up as active for everyone, chairman starts a new round, confirm new hands are dealt while old rules and penalty log are still intact.
```

### Prompt 2.4 — Multi-deck scaling, reconnects, and edge cases

```
Harden the game for real multiplayer use:

- Verify and fix multi-deck behavior end-to-end: with 2+ decks, dealing, draw pile depth, and discard reshuffling should all scale correctly across multiple rounds in the same room — add/extend tests for 2 and 3 deck games with many players, including after a round reset.
- Reconnect handling: if a player's WebSocket drops mid-game, keep their seat and hand intact, mark them "disconnected" (visible to others), and let them rejoin using the same room code + name to resume their hand, turn, and chairman status (if they were chairman) rather than starting over. If it's currently their turn while disconnected, let other players still see whose turn it is (don't auto-skip them for now).
- Edge cases to handle cleanly: a player leaves a room in the "waiting" lobby before a round starts (just remove them), the chairman disconnects (auto-transfer chairman to another connected player, same as a manual transfer, so Start Game / rule-approval / judging powers don't get stuck), a pending penalty or vote where a key participant (penalizer, target, or chairman) disconnects mid-process (define and implement a sensible fallback — e.g. auto-resolve in the disconnected party's absence, or pause and resume on reconnect — tell me which you implemented), a room with zero connected players for some time gets cleaned up from memory (simple timeout-based cleanup, e.g. 30 minutes idle).

Add or update tests for the engine-level changes, and manually verify reconnect (including mid-penalty-challenge) by closing and reopening a browser tab.
```

### Prompt 2.5 — Visual polish and deploy

```
Final pass:

Frontend polish:
- Give the table a clearer visual layout (players arranged around an oval/circle, your hand fanned at the bottom, discard pile centered), use color/suit symbols on cards, add a subtle highlight/animation when it's your turn and when a penalty is issued.
- Make it responsive enough to use on a laptop browser comfortably (mobile-friendliness is nice-to-have, not required).

Deployment:
- Prepare the backend for deployment on Render's free tier (or Fly.io if you think it fits better) — add whatever config file/Procfile is needed, document required environment variables.
- Prepare the frontend for deployment on Vercel or Netlify free tier, using an environment variable for the backend WebSocket URL instead of hardcoding localhost.
- Write a short DEPLOY.md with the exact steps to deploy both and connect them, plus how to invite friends to a room once it's live (share the room code + the deployed site URL).

Walk me through deploying it myself rather than doing it for me, since I'll need my own free-tier accounts.
```
