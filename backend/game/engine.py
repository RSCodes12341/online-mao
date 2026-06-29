from __future__ import annotations

import datetime
import random
import secrets
from dataclasses import dataclass, field
from typing import Dict, List, Optional


RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
SUITS = ["hearts", "diamonds", "clubs", "spades"]


@dataclass(frozen=True)
class Card:
    rank: str
    suit: str

    def to_dict(self) -> dict:
        return {"rank": self.rank, "suit": self.suit}


class Deck:
    def __init__(self, num_decks: int = 1) -> None:
        self.num_decks = num_decks
        self.draw_pile: List[Card] = []
        self.discard_pile: List[Card] = []
        self._build()

    def _build(self) -> None:
        cards = [
            Card(rank, suit)
            for _ in range(self.num_decks)
            for rank in RANKS
            for suit in SUITS
        ]
        random.shuffle(cards)
        self.draw_pile = cards
        self.discard_pile = []

    def deal(self, hand_size: int, num_players: int) -> List[List[Card]]:
        hands: List[List[Card]] = [[] for _ in range(num_players)]
        for _ in range(hand_size):
            for i in range(num_players):
                hands[i].append(self._draw_one())
        return hands

    def _draw_one(self) -> Card:
        if not self.draw_pile:
            self._reshuffle()
        return self.draw_pile.pop()

    def _reshuffle(self) -> None:
        if len(self.discard_pile) <= 1:
            raise RuntimeError(
                "Cannot reshuffle: discard pile has 1 or fewer cards"
            )
        top = self.discard_pile[-1]
        reshuffled = self.discard_pile[:-1]
        random.shuffle(reshuffled)
        self.draw_pile = reshuffled
        self.discard_pile = [top]

    def draw(self) -> Card:
        return self._draw_one()

    def discard(self, card: Card) -> None:
        self.discard_pile.append(card)

    def top_discard(self) -> Optional[Card]:
        return self.discard_pile[-1] if self.discard_pile else None

    def flip_first_card(self) -> Card:
        card = self._draw_one()
        self.discard_pile.append(card)
        return card


class InvalidPlay(Exception):
    pass


@dataclass
class Player:
    id: str
    display_name: str
    hand: List[Card] = field(default_factory=list)
    connected: bool = True


@dataclass
class Rule:
    id: str
    name: str
    status: str  # "active" | "pending_approval"
    proposed_by: str
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "proposed_by": self.proposed_by,
            "timestamp": self.timestamp,
        }


@dataclass
class PenaltyRecord:
    id: str
    from_player: str
    to_player: str
    reason: str             # free-form reason (can be stated aloud instead)
    cards: int              # how many cards were given at issue time
    card_objects: List[Card]  # server-side only — used for reversal on overturn
    status: str             # "issued" | "accepted" | "under_review" | "upheld" | "overturned"
    created_at: str
    resolved_at: Optional[str]
    log: List[str]          # full lifecycle narrative
    votes: Dict[str, str]   # voter_id -> "uphold" | "overturn"
    eligible_voters: List[str]  # computed once when popular vote starts

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "from_player": self.from_player,
            "to_player": self.to_player,
            "reason": self.reason,
            "cards": self.cards,
            "status": self.status,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "log": list(self.log),
            "votes": dict(self.votes),
            "eligible_voters": list(self.eligible_voters),
        }


class GameRoom:
    def __init__(self, room_id: str) -> None:
        self.room_id = room_id
        self.state: str = "waiting"
        self.players: Dict[str, Player] = {}
        self.player_order: List[str] = []
        self.current_turn_index: int = 0
        self.direction: int = 1  # +1 clockwise, -1 counterclockwise
        self.deck: Optional[Deck] = None
        self.winner: Optional[str] = None
        self.chairman_id: Optional[str] = None
        self.rules: Dict[str, Rule] = {}
        self.rejected_log: List[dict] = []
        self.penalties: Dict[str, PenaltyRecord] = {}
        self.countdown_enabled: bool = True

    # ------------------------------------------------------------------
    # Player management
    # ------------------------------------------------------------------

    def add_player(self, player_id: str, display_name: str) -> None:
        if self.state != "waiting":
            raise InvalidPlay("Cannot add player: game already started")
        if player_id in self.players:
            raise ValueError(f"Player {player_id} is already in the room")
        self.players[player_id] = Player(id=player_id, display_name=display_name)
        self.player_order.append(player_id)

    def remove_player(self, player_id: str) -> None:
        if player_id not in self.players:
            raise ValueError(f"Player {player_id} not found in room")
        idx = self.player_order.index(player_id)
        del self.players[player_id]
        self.player_order.remove(player_id)
        if self.state == "in_progress" and self.player_order:
            if self.current_turn_index >= len(self.player_order):
                self.current_turn_index = 0
            elif idx < self.current_turn_index:
                self.current_turn_index -= 1

    @property
    def current_player_id(self) -> str:
        return self.player_order[self.current_turn_index]

    @property
    def top_card(self) -> Optional[Card]:
        return self.deck.top_discard() if self.deck else None

    # ------------------------------------------------------------------
    # Game lifecycle
    # ------------------------------------------------------------------

    def start_game(self, deck_count: int = 1, hand_size: int = 5) -> None:
        if self.state != "waiting":
            raise InvalidPlay("Game has already started")
        if len(self.players) < 2:
            raise InvalidPlay("Need at least 2 players to start")
        self.deck = Deck(deck_count)
        hands = self.deck.deal(hand_size, len(self.player_order))
        for i, player_id in enumerate(self.player_order):
            self.players[player_id].hand = hands[i]
        self.deck.flip_first_card()
        self.state = "in_progress"
        self.current_turn_index = 0
        self.direction = 1

    def is_valid_play(self, player_id: str, card: Card) -> bool:
        top = self.top_card
        if top is None:
            return True
        return card.suit == top.suit or card.rank == top.rank

    def play_card(self, player_id: str, card: Card) -> None:
        if self.state != "in_progress":
            raise InvalidPlay("Game is not in progress")
        if player_id != self.current_player_id:
            raise InvalidPlay(f"It is not {player_id}'s turn")
        player = self.players[player_id]
        if card not in player.hand:
            raise InvalidPlay(f"{player_id} does not hold {card}")
        if not self.is_valid_play(player_id, card):
            raise InvalidPlay(
                f"{card} cannot be played on {self.top_card} (suit or rank must match)"
            )
        player.hand.remove(card)
        self.deck.discard(card)
        if not player.hand:
            self.state = "finished"
            self.winner = player_id
        else:
            self._advance_turn()

    def draw_card(self, player_id: str) -> Card:
        if self.state != "in_progress":
            raise InvalidPlay("Game is not in progress")
        if player_id != self.current_player_id:
            raise InvalidPlay(f"It is not {player_id}'s turn")
        card = self.deck.draw()
        self.players[player_id].hand.append(card)
        return card

    def timeout_turn(self, player_id: str) -> Card:
        """Countdown expired: draw a card and end the turn."""
        if self.state != "in_progress":
            raise InvalidPlay("Game is not in progress")
        if player_id != self.current_player_id:
            raise InvalidPlay(f"It is not {player_id}'s turn")
        card = self.deck.draw()
        self.players[player_id].hand.append(card)
        self._advance_turn()
        return card

    def set_countdown(self, player_id: str, enabled: bool) -> None:
        if self.chairman_id != player_id:
            raise InvalidPlay("Only the chairman can change the countdown setting")
        self.countdown_enabled = enabled

    def pass_turn(self, player_id: str) -> None:
        if self.state != "in_progress":
            raise InvalidPlay("Game is not in progress")
        if player_id != self.current_player_id:
            raise InvalidPlay(f"It is not {player_id}'s turn")
        self._advance_turn()

    def _advance_turn(self) -> None:
        self.current_turn_index = (
            self.current_turn_index + self.direction
        ) % len(self.player_order)

    def declare_win(self, player_id: str) -> None:
        if self.state != "in_progress":
            raise InvalidPlay("Game is not in progress")
        if player_id not in self.players:
            raise ValueError(f"Player {player_id} not found in room")
        if self.players[player_id].hand:
            raise InvalidPlay(
                f"{player_id} still has cards and cannot declare a win"
            )
        self.state = "finished"

    # ------------------------------------------------------------------
    # Chairman and rule management
    # ------------------------------------------------------------------

    def add_initial_rules(self, names: List[str], proposed_by: str) -> None:
        for name in names:
            name = name.strip()
            if not name:
                continue
            rule_id = secrets.token_urlsafe(8)
            ts = datetime.datetime.utcnow().isoformat() + "Z"
            self.rules[rule_id] = Rule(
                id=rule_id,
                name=name,
                status="active",
                proposed_by=proposed_by,
                timestamp=ts,
            )

    def propose_rule(self, player_id: str, name: str) -> Rule:
        if self.state != "waiting":
            raise InvalidPlay("Rules can only be proposed in the lobby")
        name = name.strip()
        if not name:
            raise InvalidPlay("Rule name cannot be empty")
        rule_id = secrets.token_urlsafe(8)
        ts = datetime.datetime.utcnow().isoformat() + "Z"
        rule = Rule(
            id=rule_id,
            name=name,
            status="pending_approval",
            proposed_by=player_id,
            timestamp=ts,
        )
        self.rules[rule_id] = rule
        return rule

    def review_rule(self, player_id: str, rule_id: str, decision: str) -> None:
        if self.chairman_id != player_id:
            raise InvalidPlay("Only the chairman can review rules")
        if rule_id not in self.rules:
            raise ValueError(f"Rule '{rule_id}' not found")
        rule = self.rules[rule_id]
        if rule.status != "pending_approval":
            raise InvalidPlay("Rule is not pending approval")
        if decision == "approve":
            rule.status = "active"
        elif decision == "reject":
            self.rejected_log.append({
                "id": rule.id,
                "name": rule.name,
                "proposed_by": rule.proposed_by,
                "rejected_at": datetime.datetime.utcnow().isoformat() + "Z",
            })
            del self.rules[rule_id]
        else:
            raise ValueError(f"Invalid decision: '{decision}'")

    def transfer_chairman(self, player_id: str, target_id: str) -> None:
        if self.chairman_id != player_id:
            raise InvalidPlay("Only the chairman can transfer the chairman role")
        if target_id not in self.players:
            raise ValueError(f"Player '{target_id}' not found in room")
        if not self.players[target_id].connected:
            raise InvalidPlay("Target player is not connected")
        self.chairman_id = target_id

    # ------------------------------------------------------------------
    # Penalty system
    # ------------------------------------------------------------------

    def issue_penalty(
        self, from_player: str, to_player: str, reason: str = "", cards: int = 1
    ) -> PenaltyRecord:
        if self.state != "in_progress":
            raise InvalidPlay("Penalties can only be issued during an active game")
        if from_player not in self.players:
            raise ValueError(f"Player '{from_player}' not in room")
        if to_player not in self.players:
            raise ValueError(f"Target player '{to_player}' not in room")
        if from_player == to_player:
            raise InvalidPlay("Cannot penalize yourself")
        if cards < 1:
            raise InvalidPlay("Must give at least 1 card")

        reason_display = f'"{reason}"' if reason else "(no reason stated)"

        # Cards are given immediately — this is the defining behaviour of the system.
        drawn: List[Card] = []
        for _ in range(cards):
            card = self.deck.draw()
            drawn.append(card)
            self.players[to_player].hand.append(card)

        penalty_id = secrets.token_urlsafe(8)
        ts = datetime.datetime.utcnow().isoformat() + "Z"
        record = PenaltyRecord(
            id=penalty_id,
            from_player=from_player,
            to_player=to_player,
            reason=reason,
            cards=cards,
            card_objects=drawn,
            status="issued",
            created_at=ts,
            resolved_at=None,
            log=[
                f"{from_player} penalized {to_player} — {reason_display} "
                f"({cards} card{'s' if cards != 1 else ''} added to hand immediately)"
            ],
            votes={},
            eligible_voters=[],
        )
        self.penalties[penalty_id] = record
        return record

    def respond_penalty(
        self, player_id: str, penalty_id: str, response: str
    ) -> PenaltyRecord:
        if penalty_id not in self.penalties:
            raise ValueError(f"Penalty '{penalty_id}' not found")
        record = self.penalties[penalty_id]
        if record.status != "issued":
            raise InvalidPlay("Penalty is not awaiting a response")
        if record.to_player != player_id:
            raise InvalidPlay("Only the penalized player can respond")

        ts = datetime.datetime.utcnow().isoformat() + "Z"
        if response == "accept":
            record.status = "accepted"
            record.resolved_at = ts
            record.log.append(f"{player_id} accepted the penalty")
        elif response == "reject":
            record.status = "under_review"
            if self.chairman_id != record.from_player:
                # Chairman is neutral — they judge.
                record.log.append(f"{player_id} rejected — awaiting chairman's ruling")
            else:
                # Chairman issued the penalty; popular vote among all others.
                eligible = [
                    pid for pid in self.player_order
                    if pid not in (record.from_player, record.to_player)
                    and self.players[pid].connected
                ]
                record.eligible_voters = eligible
                if not eligible:
                    # 0 eligible voters → 0-0 tie → uphold (tie rule)
                    record.log.append(
                        f"{player_id} rejected — no eligible voters; "
                        "auto-resolved as upheld (0-0 tie rule)"
                    )
                    self._resolve_penalty(record, "uphold", ts)
                else:
                    record.log.append(
                        f"{player_id} rejected — popular vote started "
                        f"({len(eligible)} eligible voter"
                        f"{'s' if len(eligible) != 1 else ''})"
                    )
        else:
            raise ValueError(f"Invalid response: '{response}'")

        return record

    def judge_penalty(
        self, player_id: str, penalty_id: str, ruling: str
    ) -> PenaltyRecord:
        if self.chairman_id != player_id:
            raise InvalidPlay("Only the chairman can judge a penalty")
        if penalty_id not in self.penalties:
            raise ValueError(f"Penalty '{penalty_id}' not found")
        record = self.penalties[penalty_id]
        if record.status != "under_review":
            raise InvalidPlay("Penalty is not under review")
        if record.from_player == self.chairman_id:
            raise InvalidPlay(
                "Chairman issued this penalty — use popular vote, not judge_penalty"
            )
        if ruling not in ("uphold", "overturn"):
            raise ValueError(f"Invalid ruling: '{ruling}'")

        ts = datetime.datetime.utcnow().isoformat() + "Z"
        record.log.append(f"Chairman {player_id} ruled: {ruling}")
        self._resolve_penalty(record, ruling, ts)
        return record

    def vote_penalty(
        self, voter_id: str, penalty_id: str, vote: str
    ) -> PenaltyRecord:
        if penalty_id not in self.penalties:
            raise ValueError(f"Penalty '{penalty_id}' not found")
        record = self.penalties[penalty_id]
        if record.status != "under_review":
            raise InvalidPlay("Penalty is not under review")
        if record.from_player != self.chairman_id:
            raise InvalidPlay(
                "Popular vote only applies when the chairman is the penalizer"
            )
        if voter_id not in record.eligible_voters:
            raise InvalidPlay(f"'{voter_id}' is not eligible to vote on this penalty")
        if voter_id in record.votes:
            raise InvalidPlay(f"'{voter_id}' has already voted")
        if vote not in ("uphold", "overturn"):
            raise ValueError(f"Invalid vote: '{vote}'")

        record.votes[voter_id] = vote
        record.log.append(f"{voter_id} voted: {vote}")

        if len(record.votes) >= len(record.eligible_voters):
            uphold_count = sum(1 for v in record.votes.values() if v == "uphold")
            overturn_count = sum(1 for v in record.votes.values() if v == "overturn")
            # NOTE: tie goes to uphold — this is adjustable per the spec request.
            ruling = "uphold" if uphold_count >= overturn_count else "overturn"
            ts = datetime.datetime.utcnow().isoformat() + "Z"
            tie_note = " (tie → uphold)" if uphold_count == overturn_count else ""
            record.log.append(
                f"Vote complete: {uphold_count} uphold, {overturn_count} overturn"
                f" → {ruling}{tie_note}"
            )
            self._resolve_penalty(record, ruling, ts)

        return record

    def _resolve_penalty(
        self, record: PenaltyRecord, ruling: str, ts: str
    ) -> None:
        if ruling == "uphold":
            # Target wrongly contested — keeps original cards plus 1 extra.
            extra = self.deck.draw()
            self.players[record.to_player].hand.append(extra)
            record.status = "upheld"
            record.resolved_at = ts
            record.log.append(
                f"Upheld: {record.to_player} keeps the {record.cards} penalty "
                f"card(s) and receives 1 extra for contesting a valid penalty"
            )
        else:  # overturn
            # Best-effort reversal: remove originally-given cards from target's hand.
            # Cards the target already played are simply skipped — no error.
            removed = 0
            for card in record.card_objects:
                if card in self.players[record.to_player].hand:
                    self.players[record.to_player].hand.remove(card)
                    self.deck.discard(card)
                    removed += 1

            # Penalizer receives 1 faulty-penalty card.
            faulty = self.deck.draw()
            self.players[record.from_player].hand.append(faulty)

            record.status = "overturned"
            record.resolved_at = ts
            if removed < record.cards:
                record.log.append(
                    f"Overturned: {removed}/{record.cards} original card(s) returned "
                    f"from {record.to_player}'s hand (rest already played); "
                    f"{record.from_player} receives 1 faulty-penalty card"
                )
            else:
                record.log.append(
                    f"Overturned: {record.cards} card(s) returned from "
                    f"{record.to_player}'s hand; "
                    f"{record.from_player} receives 1 faulty-penalty card"
                )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self, viewer_id: str) -> dict:
        players_data: Dict[str, dict] = {}
        for pid, player in self.players.items():
            entry: dict = {
                "id": player.id,
                "display_name": player.display_name,
                "hand_size": len(player.hand),
                "connected": player.connected,
            }
            if pid == viewer_id:
                entry["hand"] = [c.to_dict() for c in player.hand]
            players_data[pid] = entry

        # ── Penalty prompts personalised per viewer ──────────────────
        penalty_values = list(self.penalties.values())
        pending_penalty_response: Optional[dict] = None
        pending_judge_ruling: Optional[dict] = None
        pending_vote: Optional[dict] = None
        active_vote_tally: Optional[dict] = None

        for p in penalty_values:
            if p.status == "issued" and p.to_player == viewer_id:
                pending_penalty_response = p.to_dict()

            if p.status == "under_review":
                if self.chairman_id != p.from_player:
                    # Chairman judges this one.
                    if viewer_id == self.chairman_id:
                        pending_judge_ruling = p.to_dict()
                else:
                    # Popular vote (chairman is the penalizer).
                    if (
                        viewer_id not in (p.from_player, p.to_player)
                        and viewer_id in self.players
                        and viewer_id not in p.votes
                    ):
                        pending_vote = p.to_dict()
                    # Live tally is visible to everyone.
                    active_vote_tally = {
                        "penalty_id": p.id,
                        "uphold": sum(1 for v in p.votes.values() if v == "uphold"),
                        "overturn": sum(
                            1 for v in p.votes.values() if v == "overturn"
                        ),
                        "total_eligible": len(p.eligible_voters),
                        "total_voted": len(p.votes),
                        "reason": p.reason,
                        "from_player": p.from_player,
                        "to_player": p.to_player,
                    }

        return {
            "room_id": self.room_id,
            "state": self.state,
            "player_order": list(self.player_order),
            "current_turn_index": self.current_turn_index,
            "direction": self.direction,
            "top_card": self.top_card.to_dict() if self.top_card else None,
            "players": players_data,
            "winner": self.winner,
            "chairman_id": self.chairman_id,
            "rules": [r.to_dict() for r in self.rules.values()],
            "rejected_rules_log": list(self.rejected_log),
            "penalties": [p.to_dict() for p in penalty_values[-50:]],
            "pending_penalty_response": pending_penalty_response,
            "pending_judge_ruling": pending_judge_ruling,
            "pending_vote": pending_vote,
            "active_vote_tally": active_vote_tally,
            "countdown_enabled": self.countdown_enabled,
            "draw_pile_size": len(self.deck.draw_pile) if self.deck else 0,
            "discard_pile": [c.to_dict() for c in self.deck.discard_pile] if self.deck else [],
        }
