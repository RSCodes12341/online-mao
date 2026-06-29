# Online Mao — Game Plan

## What Mao is, for reference

Mao is a shedding card game (Uno/Crazy Eights family) where the table has secret house rules that new players must learn by trial and error and getting penalized — players are never told the full rule list up front. Each player gets a hand; on your turn you play a card matching the suit or rank of the top card. Breaking any active rule (house or hidden) earns a penalty, usually a card drawn from the deck, and the penalizer must state *what* was done wrong (not *why* it's wrong). Playing your last card requires announcing "Mao" (or the table's chosen phrase) or you get penalized. Rule sets vary wildly by group — there's no canonical list. (Source: [Wikipedia](https://en.wikipedia.org/wiki/Mao_(card_game)), [Wikibooks](https://en.wikibooks.org/wiki/Card_Games/Mao), [officialgamerules.org](https://officialgamerules.org/game-rules/mao/))

This matters for design: the engine can't hardcode "the rules of Mao" — it needs to (1) simulate a real deck faithfully, (2) give humans a fast, low-friction way to penalize each other with a stated reason, and (3) let the host maintain a living list of house rules for the table. A handful of *optional automated effects* (skip, reverse, draw-two, wild) can be built in as toggles, but the heart of the game stays player-judged, just like in person.

## Tech stack

- **Backend:** Python, FastAPI, WebSockets for real-time state sync. In-memory per-room game state (no DB needed at this scale — a friend-group app, not a production service).
- **Frontend:** React (Vite), talking to the backend over WebSocket + a couple of REST endpoints for room create/join.
- **Hosting (free tier):** Backend on Render or Fly.io (free web service), frontend on Vercel or Netlify. Single env var on the frontend pointing at the backend's WebSocket URL.

## Core architecture

**Room model:** Host creates a room → gets a short room code → friends join with the code. No fixed player cap; the host sets the number of standard 52-card decks shuffled together (1 deck for small groups, more for big ones — deal size and draw-pile depth scale automatically).

**Game engine (backend, pure Python, unit-testable, no web framework dependency):**
- `Deck`: builds N standard 52-card decks, shuffles, deals, tracks draw pile / discard pile, reshuffles discard into draw pile when it runs dry.
- `Player`: hand, name, connection id, penalty count.
- `GameRoom`: state machine (`waiting` → `in_progress` → `finished`), turn order, current direction, top-of-discard, validates a play (matches suit or rank of top card, or wild override), applies optional automated effects if the host enabled them.
- `PenaltyLog`: every penalty is `{from_player, to_player, reason, cards_added, timestamp}` — broadcast to the room and kept in a visible history.
- `RuleBook`: the room's house-rule list — free-text entries the host/players add over the course of a game ("no saying 'one'", "all eights are wild", "must tap the table on a red queen"), plus toggles for the optional built-in automated effects.

**Real-time protocol:** one WebSocket connection per player, JSON messages, server is the single source of truth for game state and rebroadcasts the full (or diffed) state after every action so clients never get out of sync — important since penalties and plays can come from any player at any time.

**Frontend:** Lobby (create/join, deck count, name), Table view (hands, discard pile, turn + direction indicator, draw button, play interaction, "Declare Mao" button), Penalty panel (pick a player, type a reason, send), Rules panel (view/add house rules, host toggles for automated effects), Game log feed (plays, penalties with reasons, rule changes, joins/leaves).

## Two-stage build plan

**Stage 1 — Core MVP.** Get a real game of shedding cards working end-to-end with friends: create/join a room, real deck simulation (any number of decks), dealing, turn-based play validated against suit/rank, drawing when stuck, declaring "Mao" to win, and a bare-bones but functional UI. No penalties or custom rules yet — just prove the multiplayer card engine is solid.

**Stage 2 — The features that make it Mao.** A "Chairman" (renamed from host, transferable to any player) sets initial rules at room creation; players can propose new rules during the lobby, which the chairman approves or rejects. Penalties cite a specific active rule, and the target must accept or reject (challenge) each one — challenges are judged by the chairman, or by a popular vote of the other players if the chairman is the one who issued the penalty. A failed challenge costs the target an extra card; a successful challenge gives the penalizer a "faulty penalty" card instead. Winning a round lets the winner add one new rule, then the room resets to the lobby with the same players and accumulated rules for another round. Also: multi-deck scaling polish, reconnect/chairman-transfer handling, visual polish, and deployment to free hosting.

Doing it in two passes means Stage 1 gives you a genuinely playable card game to test with friends before any of the Mao-specific social mechanics are layered on top — so bugs in the engine itself get caught early, separate from bugs in the penalty/rules layer.

## What's deliberately left open for later

- Which automated effects (skip/reverse/draw-two/wild) to enable by default — easiest to decide after playing Stage 1.
- Exact phrase for declaring victory ("Mao" vs. house-specific).
- Whether penalties always add exactly one card or can specify a count.
- Spectator mode, persistent accounts, game history across sessions — all out of scope unless you want to add them after Stage 2.
