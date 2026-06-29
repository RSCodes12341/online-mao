import pytest

from game.engine import Card, Deck, Player, GameRoom, InvalidPlay, RANKS, SUITS


# ---------------------------------------------------------------------------
# Card
# ---------------------------------------------------------------------------


class TestCard:
    def test_equality_same(self):
        assert Card("A", "hearts") == Card("A", "hearts")

    def test_equality_diff_suit(self):
        assert Card("A", "hearts") != Card("A", "spades")

    def test_equality_diff_rank(self):
        assert Card("A", "hearts") != Card("K", "hearts")

    def test_hashable(self):
        s = {Card("A", "hearts"), Card("A", "hearts"), Card("K", "spades")}
        assert len(s) == 2

    def test_to_dict(self):
        assert Card("K", "clubs").to_dict() == {"rank": "K", "suit": "clubs"}


# ---------------------------------------------------------------------------
# Deck
# ---------------------------------------------------------------------------


class TestDeck:
    def test_single_deck_size(self):
        d = Deck(1)
        assert len(d.draw_pile) == 52
        assert len(d.discard_pile) == 0

    def test_two_decks_size(self):
        d = Deck(2)
        assert len(d.draw_pile) == 104

    def test_three_decks_size(self):
        d = Deck(3)
        assert len(d.draw_pile) == 156

    def test_draw_removes_from_pile(self):
        d = Deck(1)
        card = d.draw()
        assert isinstance(card, Card)
        assert len(d.draw_pile) == 51

    def test_discard_adds_to_pile(self):
        d = Deck(1)
        card = d.draw()
        d.discard(card)
        assert len(d.discard_pile) == 1
        assert d.top_discard() == card

    def test_top_discard_none_when_empty(self):
        d = Deck(1)
        assert d.top_discard() is None

    def test_flip_first_card_moves_to_discard(self):
        d = Deck(1)
        card = d.flip_first_card()
        assert len(d.draw_pile) == 51
        assert len(d.discard_pile) == 1
        assert d.top_discard() == card

    def test_deal_single_deck_hand_math(self):
        d = Deck(1)
        hands = d.deal(hand_size=5, num_players=4)
        assert len(hands) == 4
        for hand in hands:
            assert len(hand) == 5
        assert len(d.draw_pile) == 52 - 20

    def test_deal_two_decks_hand_math(self):
        d = Deck(2)
        hands = d.deal(hand_size=7, num_players=6)
        assert len(hands) == 6
        for hand in hands:
            assert len(hand) == 7
        assert len(d.draw_pile) == 104 - 42

    def test_deal_cards_are_unique_single_deck(self):
        d = Deck(1)
        hands = d.deal(hand_size=5, num_players=4)
        all_cards = [c for h in hands for c in h]
        assert len(all_cards) == len(set(all_cards)), "duplicate cards dealt from single deck"

    def test_reshuffle_when_draw_pile_empty(self):
        d = Deck(1)
        # drain draw pile into discard manually (simulates many plays)
        d.discard_pile = list(d.draw_pile)
        d.draw_pile = []
        # drawing should trigger reshuffle
        card = d.draw()
        assert isinstance(card, Card)
        # total cards must still be 52
        assert len(d.draw_pile) + len(d.discard_pile) + 1 == 52

    def test_reshuffle_preserves_top_discard(self):
        d = Deck(1)
        all_cards = list(d.draw_pile)
        top = all_cards[-1]
        d.discard_pile = all_cards
        d.draw_pile = []
        d.draw()
        assert d.top_discard() == top

    def test_reshuffle_fails_with_single_discard_card(self):
        d = Deck(1)
        d.discard_pile = [Card("A", "hearts")]
        d.draw_pile = []
        with pytest.raises(RuntimeError):
            d.draw()

    def test_reshuffle_fails_with_empty_discard(self):
        d = Deck(1)
        d.draw_pile = []
        d.discard_pile = []
        with pytest.raises(RuntimeError):
            d.draw()


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------


class TestPlayer:
    def test_defaults(self):
        p = Player(id="p1", display_name="Alice")
        assert p.hand == []
        assert p.connected is True

    def test_fields(self):
        card = Card("5", "clubs")
        p = Player(id="p2", display_name="Bob", hand=[card], connected=False)
        assert p.hand == [card]
        assert not p.connected


# ---------------------------------------------------------------------------
# GameRoom helpers
# ---------------------------------------------------------------------------


def make_room(*names: str) -> GameRoom:
    room = GameRoom("test-room")
    for i, name in enumerate(names):
        room.add_player(f"p{i + 1}", name)
    return room


def start_room(*names: str, deck_count: int = 1, hand_size: int = 5) -> GameRoom:
    room = make_room(*names)
    room.start_game(deck_count=deck_count, hand_size=hand_size)
    return room


def valid_card_for_top(top: Card) -> Card:
    """Return a card that matches top by suit but with a different rank."""
    other_rank = next(r for r in RANKS if r != top.rank)
    return Card(other_rank, top.suit)


def invalid_card_for_top(top: Card) -> Card:
    """Return a card that matches neither suit nor rank of top."""
    other_rank = next(r for r in RANKS if r != top.rank)
    other_suit = next(s for s in SUITS if s != top.suit)
    return Card(other_rank, other_suit)


# ---------------------------------------------------------------------------
# GameRoom — player management
# ---------------------------------------------------------------------------


class TestGameRoomPlayers:
    def test_add_player(self):
        room = GameRoom("r1")
        room.add_player("p1", "Alice")
        assert "p1" in room.players
        assert room.players["p1"].display_name == "Alice"
        assert room.player_order == ["p1"]

    def test_add_duplicate_player_raises(self):
        room = make_room("Alice")
        with pytest.raises(ValueError):
            room.add_player("p1", "Alice Again")

    def test_add_player_after_game_started_raises(self):
        room = start_room("Alice", "Bob")
        with pytest.raises(InvalidPlay):
            room.add_player("p3", "Charlie")

    def test_remove_player_waiting(self):
        room = make_room("Alice", "Bob")
        room.remove_player("p2")
        assert "p2" not in room.players
        assert "p2" not in room.player_order

    def test_remove_nonexistent_player_raises(self):
        room = make_room("Alice")
        with pytest.raises(ValueError):
            room.remove_player("ghost")

    def test_remove_player_adjusts_turn_index(self):
        room = GameRoom("r1")
        room.add_player("p1", "Alice")
        room.add_player("p2", "Bob")
        room.add_player("p3", "Charlie")
        room.start_game()
        # advance to p2's turn
        room.current_turn_index = 1
        # remove p1 (index 0 < current 1) -> current_turn_index must decrease
        room.remove_player("p1")
        assert room.current_turn_index == 0
        assert room.current_player_id == "p2"


# ---------------------------------------------------------------------------
# GameRoom — start_game
# ---------------------------------------------------------------------------


class TestStartGame:
    def test_start_game_changes_state(self):
        room = start_room("Alice", "Bob")
        assert room.state == "in_progress"

    def test_start_game_deals_correct_hand_size(self):
        room = start_room("Alice", "Bob", "Charlie", hand_size=7)
        for pid in room.player_order:
            assert len(room.players[pid].hand) == 7

    def test_start_game_flips_top_card(self):
        room = start_room("Alice", "Bob")
        assert room.top_card is not None
        assert isinstance(room.top_card, Card)

    def test_start_game_dealing_math_two_decks(self):
        room = GameRoom("r1")
        for i in range(4):
            room.add_player(f"p{i + 1}", f"Player {i + 1}")
        room.start_game(deck_count=2, hand_size=5)
        # 104 total - 20 dealt - 1 flip = 83
        assert len(room.deck.draw_pile) == 83
        assert len(room.deck.discard_pile) == 1

    def test_start_game_requires_two_players(self):
        room = make_room("Alice")
        with pytest.raises(InvalidPlay):
            room.start_game()

    def test_start_game_twice_raises(self):
        room = start_room("Alice", "Bob")
        with pytest.raises(InvalidPlay):
            room.start_game()

    def test_initial_direction_is_clockwise(self):
        room = start_room("Alice", "Bob")
        assert room.direction == 1

    def test_initial_turn_index_is_zero(self):
        room = start_room("Alice", "Bob")
        assert room.current_turn_index == 0


# ---------------------------------------------------------------------------
# GameRoom — is_valid_play
# ---------------------------------------------------------------------------


class TestIsValidPlay:
    def test_same_suit_is_valid(self):
        room = start_room("Alice", "Bob")
        top = room.top_card
        assert room.is_valid_play("p1", Card(next(r for r in RANKS if r != top.rank), top.suit))

    def test_same_rank_is_valid(self):
        room = start_room("Alice", "Bob")
        top = room.top_card
        other_suit = next(s for s in SUITS if s != top.suit)
        assert room.is_valid_play("p1", Card(top.rank, other_suit))

    def test_different_rank_and_suit_is_invalid(self):
        room = start_room("Alice", "Bob")
        top = room.top_card
        assert not room.is_valid_play("p1", invalid_card_for_top(top))


# ---------------------------------------------------------------------------
# GameRoom — play_card
# ---------------------------------------------------------------------------


class TestPlayCard:
    def test_valid_play_removes_card_from_hand(self):
        room = start_room("Alice", "Bob")
        pid = room.current_player_id
        card = valid_card_for_top(room.top_card)
        room.players[pid].hand.append(card)
        hand_before = len(room.players[pid].hand)
        room.play_card(pid, card)
        assert len(room.players[pid].hand) == hand_before - 1

    def test_valid_play_updates_top_card(self):
        room = start_room("Alice", "Bob")
        pid = room.current_player_id
        card = valid_card_for_top(room.top_card)
        room.players[pid].hand.append(card)
        room.play_card(pid, card)
        assert room.top_card == card

    def test_valid_play_advances_turn(self):
        room = start_room("Alice", "Bob")
        first = room.current_player_id
        card = valid_card_for_top(room.top_card)
        room.players[first].hand.append(card)
        room.play_card(first, card)
        assert room.current_player_id != first

    def test_invalid_card_raises(self):
        room = start_room("Alice", "Bob")
        pid = room.current_player_id
        bad = invalid_card_for_top(room.top_card)
        room.players[pid].hand.append(bad)
        with pytest.raises(InvalidPlay):
            room.play_card(pid, bad)

    def test_card_not_in_hand_raises(self):
        room = start_room("Alice", "Bob")
        pid = room.current_player_id
        top = room.top_card
        hand = set(room.players[pid].hand)
        # pick a card valid to play that is definitively not in the player's hand
        card = next(
            Card(r, top.suit) for r in RANKS
            if r != top.rank and Card(r, top.suit) not in hand
        )
        with pytest.raises(InvalidPlay):
            room.play_card(pid, card)

    def test_wrong_player_raises(self):
        room = start_room("Alice", "Bob")
        first = room.current_player_id
        other = next(p for p in room.player_order if p != first)
        card = valid_card_for_top(room.top_card)
        room.players[other].hand.append(card)
        with pytest.raises(InvalidPlay):
            room.play_card(other, card)

    def test_play_when_not_in_progress_raises(self):
        room = make_room("Alice", "Bob")
        with pytest.raises(InvalidPlay):
            room.play_card("p1", Card("A", "hearts"))


# ---------------------------------------------------------------------------
# GameRoom — draw_card
# ---------------------------------------------------------------------------


class TestDrawCard:
    def test_draw_adds_card_to_hand(self):
        room = start_room("Alice", "Bob")
        pid = room.current_player_id
        before = len(room.players[pid].hand)
        room.draw_card(pid)
        assert len(room.players[pid].hand) == before + 1

    def test_draw_advances_turn(self):
        room = start_room("Alice", "Bob")
        first = room.current_player_id
        room.draw_card(first)
        assert room.current_player_id != first

    def test_draw_wrong_player_raises(self):
        room = start_room("Alice", "Bob")
        first = room.current_player_id
        other = next(p for p in room.player_order if p != first)
        with pytest.raises(InvalidPlay):
            room.draw_card(other)

    def test_draw_when_not_in_progress_raises(self):
        room = make_room("Alice", "Bob")
        with pytest.raises(InvalidPlay):
            room.draw_card("p1")


# ---------------------------------------------------------------------------
# GameRoom — turn order
# ---------------------------------------------------------------------------


class TestTurnOrder:
    def test_turn_wraps_around_three_players(self):
        room = start_room("Alice", "Bob", "Charlie")
        order = list(room.player_order)
        for expected in order * 2:  # two full cycles
            assert room.current_player_id == expected
            room.draw_card(room.current_player_id)

    def test_counterclockwise_direction(self):
        room = start_room("Alice", "Bob", "Charlie")
        room.direction = -1
        room.current_turn_index = 0
        first = room.current_player_id  # p1
        room.draw_card(first)
        # (0 + -1) % 3 == 2  -> last player
        assert room.current_player_id == room.player_order[2]

    def test_direction_clockwise_two_players(self):
        room = start_room("Alice", "Bob")
        first = room.current_player_id
        room.draw_card(first)
        second = room.current_player_id
        room.draw_card(second)
        assert room.current_player_id == first  # back to first


# ---------------------------------------------------------------------------
# GameRoom — declare_win
# ---------------------------------------------------------------------------


class TestDeclareWin:
    def test_declare_win_with_empty_hand(self):
        room = start_room("Alice", "Bob")
        pid = room.current_player_id
        room.players[pid].hand = []
        room.declare_win(pid)
        assert room.state == "finished"

    def test_declare_win_with_cards_raises(self):
        room = start_room("Alice", "Bob")
        pid = room.current_player_id
        with pytest.raises(InvalidPlay):
            room.declare_win(pid)

    def test_declare_win_not_in_progress_raises(self):
        room = make_room("Alice", "Bob")
        with pytest.raises(InvalidPlay):
            room.declare_win("p1")

    def test_declare_win_unknown_player_raises(self):
        room = start_room("Alice", "Bob")
        with pytest.raises(ValueError):
            room.declare_win("ghost")


# ---------------------------------------------------------------------------
# GameRoom — auto-win via play_card
# ---------------------------------------------------------------------------


class TestAutoWin:
    def test_play_last_card_finishes_game(self):
        room = start_room("Alice", "Bob")
        pid = room.current_player_id
        card = valid_card_for_top(room.top_card)
        room.players[pid].hand = [card]
        room.play_card(pid, card)
        assert room.state == "finished"

    def test_play_last_card_sets_winner(self):
        room = start_room("Alice", "Bob")
        pid = room.current_player_id
        card = valid_card_for_top(room.top_card)
        room.players[pid].hand = [card]
        room.play_card(pid, card)
        assert room.winner == pid

    def test_play_non_last_card_does_not_finish(self):
        room = start_room("Alice", "Bob")
        pid = room.current_player_id
        card = valid_card_for_top(room.top_card)
        room.players[pid].hand.append(card)
        assert len(room.players[pid].hand) >= 2
        room.play_card(pid, card)
        assert room.state == "in_progress"
        assert room.winner is None

    def test_play_last_card_does_not_advance_turn(self):
        room = start_room("Alice", "Bob")
        pid = room.current_player_id
        card = valid_card_for_top(room.top_card)
        room.players[pid].hand = [card]
        room.play_card(pid, card)
        assert room.current_turn_index == 0  # unchanged; game is over

    def test_winner_in_to_dict(self):
        room = start_room("Alice", "Bob")
        pid = room.current_player_id
        card = valid_card_for_top(room.top_card)
        room.players[pid].hand = [card]
        room.play_card(pid, card)
        d = room.to_dict(pid)
        assert d["winner"] == pid
        assert d["state"] == "finished"


# ---------------------------------------------------------------------------
# GameRoom — to_dict
# ---------------------------------------------------------------------------


class TestToDict:
    def test_viewer_sees_own_hand(self):
        room = start_room("Alice", "Bob")
        d = room.to_dict("p1")
        assert "hand" in d["players"]["p1"]
        assert isinstance(d["players"]["p1"]["hand"], list)

    def test_viewer_does_not_see_other_hands(self):
        room = start_room("Alice", "Bob")
        d = room.to_dict("p1")
        assert "hand" not in d["players"]["p2"]

    def test_all_players_have_hand_size(self):
        room = start_room("Alice", "Bob", "Charlie")
        d = room.to_dict("p1")
        for pid in ["p1", "p2", "p3"]:
            assert "hand_size" in d["players"][pid]

    def test_hand_size_matches_actual_hand(self):
        room = start_room("Alice", "Bob")
        d = room.to_dict("p1")
        assert d["players"]["p1"]["hand_size"] == len(room.players["p1"].hand)

    def test_top_card_in_dict(self):
        room = start_room("Alice", "Bob")
        d = room.to_dict("p1")
        assert d["top_card"] == room.top_card.to_dict()

    def test_structure(self):
        room = start_room("Alice", "Bob")
        d = room.to_dict("p1")
        for key in (
            "room_id", "state", "player_order", "current_turn_index", "direction",
            "top_card", "players", "winner", "chairman_id", "rules", "rejected_rules_log",
            "penalties", "pending_penalty_response", "pending_judge_ruling",
            "pending_vote", "active_vote_tally",
        ):
            assert key in d

    def test_waiting_state_top_card_none(self):
        room = make_room("Alice", "Bob")
        d = room.to_dict("p1")
        assert d["top_card"] is None
        assert d["state"] == "waiting"
        assert d["winner"] is None


# ---------------------------------------------------------------------------
# Integration: draw pile reshuffle during live game
# ---------------------------------------------------------------------------


class TestReshuffleDuringGame:
    def test_reshuffle_happens_transparently(self):
        room = start_room("Alice", "Bob", deck_count=1, hand_size=5)
        # Drain most of the draw pile into the discard pile directly
        # Keep at least 2 cards in discard (top + 1 more) so reshuffle can work
        room.deck.draw_pile = []
        room.deck.discard_pile = [room.deck.discard_pile[-1]] + [Card("3", "hearts")] * 20

        # Drawing should reshuffle transparently
        pid = room.current_player_id
        card = room.draw_card(pid)
        assert isinstance(card, Card)


# ---------------------------------------------------------------------------
# Chairman role
# ---------------------------------------------------------------------------


class TestChairman:
    def test_chairman_initially_none(self):
        room = GameRoom("r1")
        assert room.chairman_id is None

    def test_transfer_chairman(self):
        room = make_room("Alice", "Bob")
        room.chairman_id = "p1"
        room.transfer_chairman("p1", "p2")
        assert room.chairman_id == "p2"

    def test_transfer_non_chairman_raises(self):
        room = make_room("Alice", "Bob")
        room.chairman_id = "p1"
        with pytest.raises(InvalidPlay):
            room.transfer_chairman("p2", "p1")

    def test_transfer_to_disconnected_raises(self):
        room = make_room("Alice", "Bob")
        room.chairman_id = "p1"
        room.players["p2"].connected = False
        with pytest.raises(InvalidPlay):
            room.transfer_chairman("p1", "p2")

    def test_transfer_to_unknown_player_raises(self):
        room = make_room("Alice", "Bob")
        room.chairman_id = "p1"
        with pytest.raises(ValueError):
            room.transfer_chairman("p1", "ghost")

    def test_to_dict_includes_chairman_id(self):
        room = make_room("Alice", "Bob")
        room.chairman_id = "p1"
        d = room.to_dict("p1")
        assert d["chairman_id"] == "p1"


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


class TestRules:
    def test_add_initial_rules(self):
        room = GameRoom("r1")
        room.add_initial_rules(["No talking", "No laughing"], "alice")
        assert len(room.rules) == 2
        for rule in room.rules.values():
            assert rule.status == "active"
            assert rule.proposed_by == "alice"

    def test_add_initial_rules_skips_blank(self):
        room = GameRoom("r1")
        room.add_initial_rules(["  ", "Valid rule", ""], "alice")
        assert len(room.rules) == 1

    def test_propose_rule_creates_pending(self):
        room = make_room("Alice", "Bob")
        rule = room.propose_rule("p1", "No drawing twice")
        assert rule.status == "pending_approval"
        assert rule.id in room.rules

    def test_propose_rule_not_in_waiting_raises(self):
        room = start_room("Alice", "Bob")
        with pytest.raises(InvalidPlay):
            room.propose_rule("p1", "Some rule")

    def test_propose_empty_rule_raises(self):
        room = make_room("Alice", "Bob")
        with pytest.raises(InvalidPlay):
            room.propose_rule("p1", "   ")

    def test_review_approve(self):
        room = make_room("Alice", "Bob")
        room.chairman_id = "p1"
        rule = room.propose_rule("p2", "No yelling")
        room.review_rule("p1", rule.id, "approve")
        assert room.rules[rule.id].status == "active"

    def test_review_reject_removes_rule(self):
        room = make_room("Alice", "Bob")
        room.chairman_id = "p1"
        rule = room.propose_rule("p2", "No yelling")
        room.review_rule("p1", rule.id, "reject")
        assert rule.id not in room.rules

    def test_review_reject_logs_entry(self):
        room = make_room("Alice", "Bob")
        room.chairman_id = "p1"
        rule = room.propose_rule("p2", "No yelling")
        room.review_rule("p1", rule.id, "reject")
        assert len(room.rejected_log) == 1
        assert room.rejected_log[0]["name"] == "No yelling"
        assert room.rejected_log[0]["proposed_by"] == "p2"

    def test_review_non_chairman_raises(self):
        room = make_room("Alice", "Bob")
        room.chairman_id = "p1"
        rule = room.propose_rule("p1", "No yelling")
        with pytest.raises(InvalidPlay):
            room.review_rule("p2", rule.id, "approve")

    def test_review_invalid_decision_raises(self):
        room = make_room("Alice", "Bob")
        room.chairman_id = "p1"
        rule = room.propose_rule("p2", "No yelling")
        with pytest.raises(ValueError):
            room.review_rule("p1", rule.id, "maybe")

    def test_review_already_active_raises(self):
        room = make_room("Alice", "Bob")
        room.chairman_id = "p1"
        room.add_initial_rules(["Active rule"], "p1")
        rule_id = next(iter(room.rules))
        with pytest.raises(InvalidPlay):
            room.review_rule("p1", rule_id, "approve")

    def test_review_unknown_rule_raises(self):
        room = make_room("Alice", "Bob")
        room.chairman_id = "p1"
        with pytest.raises(ValueError):
            room.review_rule("p1", "nonexistent", "approve")

    def test_to_dict_includes_rules(self):
        room = make_room("Alice", "Bob")
        room.chairman_id = "p1"
        room.add_initial_rules(["Active rule"], "p1")
        d = room.to_dict("p1")
        assert len(d["rules"]) == 1
        assert d["rules"][0]["status"] == "active"
        assert d["rejected_rules_log"] == []

    def test_to_dict_rejected_log_appears(self):
        room = make_room("Alice", "Bob")
        room.chairman_id = "p1"
        rule = room.propose_rule("p2", "Bad rule")
        room.review_rule("p1", rule.id, "reject")
        d = room.to_dict("p1")
        assert len(d["rejected_rules_log"]) == 1

    def test_new_chairman_can_review_after_transfer(self):
        room = make_room("Alice", "Bob")
        room.chairman_id = "p1"
        rule = room.propose_rule("p1", "Some rule")
        room.transfer_chairman("p1", "p2")
        room.review_rule("p2", rule.id, "approve")
        assert room.rules[rule.id].status == "active"

# ---------------------------------------------------------------------------
# Penalties — helpers
# ---------------------------------------------------------------------------


def _room_with_penalty_setup(*names: str):
    """Returned room is in_progress, chairman=p1, one active rule already set."""
    room = start_room(*names)
    room.chairman_id = "p1"
    room.add_initial_rules(["No talking"], "p1")
    rule_id = next(iter(room.rules))
    return room, rule_id


# ---------------------------------------------------------------------------
# Penalties — issuance
# ---------------------------------------------------------------------------


class TestPenaltyIssuance:
    def test_issue_adds_card_to_target_immediately(self):
        room, rule_id = _room_with_penalty_setup("Alice", "Bob")
        before = len(room.players["p2"].hand)
        room.issue_penalty("p1", "p2", rule_id)
        assert len(room.players["p2"].hand) == before + 1

    def test_issue_multiple_cards(self):
        room, rule_id = _room_with_penalty_setup("Alice", "Bob")
        before = len(room.players["p2"].hand)
        room.issue_penalty("p1", "p2", rule_id, cards=3)
        assert len(room.players["p2"].hand) == before + 3

    def test_issue_records_correct_fields(self):
        room, rule_id = _room_with_penalty_setup("Alice", "Bob")
        p = room.issue_penalty("p1", "p2", rule_id, cards=2)
        assert p.from_player == "p1"
        assert p.to_player == "p2"
        assert p.rule_id == rule_id
        assert p.rule_name == "No talking"
        assert p.cards == 2
        assert p.status == "issued"
        assert len(p.card_objects) == 2
        assert p.id in room.penalties

    def test_issue_self_raises(self):
        room, rule_id = _room_with_penalty_setup("Alice", "Bob")
        with pytest.raises(InvalidPlay):
            room.issue_penalty("p1", "p1", rule_id)

    def test_issue_unknown_target_raises(self):
        room, rule_id = _room_with_penalty_setup("Alice", "Bob")
        with pytest.raises(ValueError):
            room.issue_penalty("p1", "ghost", rule_id)

    def test_issue_unknown_rule_raises(self):
        room, rule_id = _room_with_penalty_setup("Alice", "Bob")
        with pytest.raises(InvalidPlay):
            room.issue_penalty("p1", "p2", "bad-rule-id")

    def test_issue_inactive_rule_raises(self):
        room, rule_id = _room_with_penalty_setup("Alice", "Bob")
        room.rules[rule_id].status = "pending_approval"
        with pytest.raises(InvalidPlay):
            room.issue_penalty("p1", "p2", rule_id)

    def test_issue_not_in_progress_raises(self):
        room = make_room("Alice", "Bob")
        room.chairman_id = "p1"
        room.add_initial_rules(["No talking"], "p1")
        rule_id = next(iter(room.rules))
        with pytest.raises(InvalidPlay):
            room.issue_penalty("p1", "p2", rule_id)

    def test_issue_zero_cards_raises(self):
        room, rule_id = _room_with_penalty_setup("Alice", "Bob")
        with pytest.raises(InvalidPlay):
            room.issue_penalty("p1", "p2", rule_id, cards=0)

    def test_any_player_can_penalize(self):
        room, rule_id = _room_with_penalty_setup("Alice", "Bob")
        before = len(room.players["p1"].hand)
        room.issue_penalty("p2", "p1", rule_id)
        assert len(room.players["p1"].hand) == before + 1


# ---------------------------------------------------------------------------
# Penalties — accept path
# ---------------------------------------------------------------------------


class TestPenaltyAccept:
    def test_accept_status(self):
        room, rule_id = _room_with_penalty_setup("Alice", "Bob")
        p = room.issue_penalty("p1", "p2", rule_id)
        room.respond_penalty("p2", p.id, "accept")
        assert p.status == "accepted"
        assert p.resolved_at is not None

    def test_accept_no_additional_card_change(self):
        room, rule_id = _room_with_penalty_setup("Alice", "Bob")
        p = room.issue_penalty("p1", "p2", rule_id)
        hand_after_issue = len(room.players["p2"].hand)
        room.respond_penalty("p2", p.id, "accept")
        assert len(room.players["p2"].hand) == hand_after_issue

    def test_accept_wrong_player_raises(self):
        room, rule_id = _room_with_penalty_setup("Alice", "Bob")
        p = room.issue_penalty("p1", "p2", rule_id)
        with pytest.raises(InvalidPlay):
            room.respond_penalty("p1", p.id, "accept")

    def test_accept_already_resolved_raises(self):
        room, rule_id = _room_with_penalty_setup("Alice", "Bob")
        p = room.issue_penalty("p1", "p2", rule_id)
        room.respond_penalty("p2", p.id, "accept")
        with pytest.raises(InvalidPlay):
            room.respond_penalty("p2", p.id, "accept")

    def test_respond_invalid_response_raises(self):
        room, rule_id = _room_with_penalty_setup("Alice", "Bob")
        p = room.issue_penalty("p1", "p2", rule_id)
        with pytest.raises(ValueError):
            room.respond_penalty("p2", p.id, "maybe")


# ---------------------------------------------------------------------------
# Penalties — reject → chairman judges
# ---------------------------------------------------------------------------


class TestPenaltyChairmanJudge:
    # Setup: p1=chairman (neutral), p2 penalizes p3 → p1 judges
    def _judge_setup(self):
        room = start_room("Alice", "Bob", "Charlie")
        room.chairman_id = "p1"
        room.add_initial_rules(["No talking"], "p1")
        rule_id = next(iter(room.rules))
        return room, rule_id

    def test_reject_routes_to_under_review(self):
        room, rule_id = self._judge_setup()
        p = room.issue_penalty("p2", "p3", rule_id)
        room.respond_penalty("p3", p.id, "reject")
        assert p.status == "under_review"

    def test_chairman_judge_path_has_no_eligible_voters(self):
        room, rule_id = self._judge_setup()
        p = room.issue_penalty("p2", "p3", rule_id)
        room.respond_penalty("p3", p.id, "reject")
        assert p.eligible_voters == []

    def test_chairman_uphold_adds_extra_card(self):
        room, rule_id = self._judge_setup()
        p = room.issue_penalty("p2", "p3", rule_id)
        hand_after_issue = len(room.players["p3"].hand)
        room.respond_penalty("p3", p.id, "reject")
        room.judge_penalty("p1", p.id, "uphold")
        assert p.status == "upheld"
        assert len(room.players["p3"].hand) == hand_after_issue + 1

    def test_chairman_overturn_removes_card_from_target(self):
        room, rule_id = self._judge_setup()
        hand_before_penalty = len(room.players["p3"].hand)
        p = room.issue_penalty("p2", "p3", rule_id)
        room.respond_penalty("p3", p.id, "reject")
        room.judge_penalty("p1", p.id, "overturn")
        assert p.status == "overturned"
        assert len(room.players["p3"].hand) == hand_before_penalty

    def test_chairman_overturn_gives_penalizer_faulty_card(self):
        room, rule_id = self._judge_setup()
        penalizer_before = len(room.players["p2"].hand)
        p = room.issue_penalty("p2", "p3", rule_id)
        room.respond_penalty("p3", p.id, "reject")
        room.judge_penalty("p1", p.id, "overturn")
        assert len(room.players["p2"].hand) == penalizer_before + 1

    def test_non_chairman_cannot_judge(self):
        room, rule_id = self._judge_setup()
        p = room.issue_penalty("p2", "p3", rule_id)
        room.respond_penalty("p3", p.id, "reject")
        with pytest.raises(InvalidPlay):
            room.judge_penalty("p2", p.id, "uphold")  # p2 is not chairman

    def test_chairman_cannot_judge_own_penalty(self):
        room = start_room("Alice", "Bob", "Charlie")
        room.chairman_id = "p1"
        room.add_initial_rules(["No talking"], "p1")
        rule_id = next(iter(room.rules))
        p = room.issue_penalty("p1", "p2", rule_id)  # chairman penalizes → vote path
        room.respond_penalty("p2", p.id, "reject")
        with pytest.raises(InvalidPlay):
            room.judge_penalty("p1", p.id, "uphold")

    def test_judge_invalid_ruling_raises(self):
        room, rule_id = self._judge_setup()
        p = room.issue_penalty("p2", "p3", rule_id)
        room.respond_penalty("p3", p.id, "reject")
        with pytest.raises(ValueError):
            room.judge_penalty("p1", p.id, "maybe")

    def test_judge_not_under_review_raises(self):
        room, rule_id = self._judge_setup()
        p = room.issue_penalty("p2", "p3", rule_id)  # still "issued"
        with pytest.raises(InvalidPlay):
            room.judge_penalty("p1", p.id, "uphold")


# ---------------------------------------------------------------------------
# Penalties — reject → popular vote (chairman is penalizer)
# ---------------------------------------------------------------------------


class TestPenaltyPopularVote:
    def _vote_room(self):
        room = start_room("Alice", "Bob", "Charlie")
        room.chairman_id = "p1"
        room.add_initial_rules(["No talking"], "p1")
        rule_id = next(iter(room.rules))
        return room, rule_id

    def test_popular_vote_sets_eligible_voters(self):
        room, rule_id = self._vote_room()
        p = room.issue_penalty("p1", "p2", rule_id)
        room.respond_penalty("p2", p.id, "reject")
        assert "p3" in p.eligible_voters
        assert "p1" not in p.eligible_voters
        assert "p2" not in p.eligible_voters

    def test_popular_vote_uphold_gives_extra_card(self):
        room, rule_id = self._vote_room()
        p = room.issue_penalty("p1", "p2", rule_id)
        hand_after_issue = len(room.players["p2"].hand)
        room.respond_penalty("p2", p.id, "reject")
        room.vote_penalty("p3", p.id, "uphold")
        assert p.status == "upheld"
        assert len(room.players["p2"].hand) == hand_after_issue + 1

    def test_popular_vote_overturn_removes_card_from_target(self):
        room, rule_id = self._vote_room()
        hand_before_penalty = len(room.players["p2"].hand)
        p = room.issue_penalty("p1", "p2", rule_id)
        room.respond_penalty("p2", p.id, "reject")
        room.vote_penalty("p3", p.id, "overturn")
        assert p.status == "overturned"
        assert len(room.players["p2"].hand) == hand_before_penalty

    def test_popular_vote_overturn_gives_penalizer_faulty_card(self):
        room, rule_id = self._vote_room()
        penalizer_before = len(room.players["p1"].hand)
        p = room.issue_penalty("p1", "p2", rule_id)
        room.respond_penalty("p2", p.id, "reject")
        room.vote_penalty("p3", p.id, "overturn")
        assert len(room.players["p1"].hand) == penalizer_before + 1

    def test_popular_vote_tie_upholds(self):
        room = start_room("Alice", "Bob", "Charlie", "Dave")
        room.chairman_id = "p1"
        room.add_initial_rules(["No talking"], "p1")
        rule_id = next(iter(room.rules))
        p = room.issue_penalty("p1", "p2", rule_id)
        room.respond_penalty("p2", p.id, "reject")
        assert set(p.eligible_voters) == {"p3", "p4"}
        room.vote_penalty("p3", p.id, "uphold")
        room.vote_penalty("p4", p.id, "overturn")  # 1-1 tie
        assert p.status == "upheld"
        assert any("tie" in entry for entry in p.log)

    def test_vote_resolves_only_when_all_voted(self):
        room = start_room("Alice", "Bob", "Charlie", "Dave")
        room.chairman_id = "p1"
        room.add_initial_rules(["No talking"], "p1")
        rule_id = next(iter(room.rules))
        p = room.issue_penalty("p1", "p2", rule_id)
        room.respond_penalty("p2", p.id, "reject")
        room.vote_penalty("p3", p.id, "uphold")
        assert p.status == "under_review"  # p4 hasn't voted
        room.vote_penalty("p4", p.id, "uphold")
        assert p.status == "upheld"

    def test_duplicate_vote_raises(self):
        room, rule_id = self._vote_room()
        p = room.issue_penalty("p1", "p2", rule_id)
        room.respond_penalty("p2", p.id, "reject")
        room.vote_penalty("p3", p.id, "uphold")
        with pytest.raises(InvalidPlay):
            room.vote_penalty("p3", p.id, "uphold")

    def test_ineligible_voter_raises(self):
        room, rule_id = self._vote_room()
        p = room.issue_penalty("p1", "p2", rule_id)
        room.respond_penalty("p2", p.id, "reject")
        with pytest.raises(InvalidPlay):
            room.vote_penalty("p1", p.id, "uphold")

    def test_invalid_vote_value_raises(self):
        room, rule_id = self._vote_room()
        p = room.issue_penalty("p1", "p2", rule_id)
        room.respond_penalty("p2", p.id, "reject")
        with pytest.raises(ValueError):
            room.vote_penalty("p3", p.id, "maybe")

    def test_no_eligible_voters_auto_upholds(self):
        room = start_room("Alice", "Bob")
        room.chairman_id = "p1"
        room.add_initial_rules(["No talking"], "p1")
        rule_id = next(iter(room.rules))
        p = room.issue_penalty("p1", "p2", rule_id)
        room.respond_penalty("p2", p.id, "reject")
        assert p.status == "upheld"
        assert any("auto-resolved" in entry for entry in p.log)


# ---------------------------------------------------------------------------
# Penalties — overturn edge case: card already played
# ---------------------------------------------------------------------------


class TestPenaltyOverturnEdgeCase:
    def test_partial_reversal_when_card_played(self):
        # p1=chairman (neutral), p2 penalizes p3, p1 judges
        room = start_room("Alice", "Bob", "Charlie")
        room.chairman_id = "p1"
        room.add_initial_rules(["No talking"], "p1")
        rule_id = next(iter(room.rules))
        p = room.issue_penalty("p2", "p3", rule_id)
        penalty_card = p.card_objects[0]
        room.respond_penalty("p3", p.id, "reject")
        # Simulate: target plays the penalty card during the review window
        if penalty_card in room.players["p3"].hand:
            room.players["p3"].hand.remove(penalty_card)
        hand_before_overturn = len(room.players["p3"].hand)
        penalizer_before = len(room.players["p2"].hand)
        room.judge_penalty("p1", p.id, "overturn")
        assert p.status == "overturned"
        # 0 cards removed (card was already gone)
        assert len(room.players["p3"].hand) == hand_before_overturn
        # Penalizer still receives the faulty-penalty card
        assert len(room.players["p2"].hand) == penalizer_before + 1
        assert any("0/1" in entry for entry in p.log)


# ---------------------------------------------------------------------------
# Penalties — to_dict personalisation
# ---------------------------------------------------------------------------


class TestPenaltyToDict:
    def test_pending_penalty_response_shown_to_target(self):
        room, rule_id = _room_with_penalty_setup("Alice", "Bob")
        p = room.issue_penalty("p1", "p2", rule_id)
        d = room.to_dict("p2")
        assert d["pending_penalty_response"] is not None
        assert d["pending_penalty_response"]["id"] == p.id

    def test_pending_penalty_response_hidden_from_others(self):
        room, rule_id = _room_with_penalty_setup("Alice", "Bob")
        room.issue_penalty("p1", "p2", rule_id)
        d = room.to_dict("p1")
        assert d["pending_penalty_response"] is None

    def test_pending_judge_ruling_shown_to_chairman(self):
        # p1=chairman (neutral), p2 penalizes p3 → p1 gets judge prompt
        room = start_room("Alice", "Bob", "Charlie")
        room.chairman_id = "p1"
        room.add_initial_rules(["No talking"], "p1")
        rule_id = next(iter(room.rules))
        p = room.issue_penalty("p2", "p3", rule_id)
        room.respond_penalty("p3", p.id, "reject")
        d = room.to_dict("p1")
        assert d["pending_judge_ruling"] is not None
        assert d["pending_judge_ruling"]["id"] == p.id

    def test_pending_judge_ruling_hidden_from_non_chairman(self):
        room = start_room("Alice", "Bob", "Charlie")
        room.chairman_id = "p1"
        room.add_initial_rules(["No talking"], "p1")
        rule_id = next(iter(room.rules))
        p = room.issue_penalty("p2", "p3", rule_id)
        room.respond_penalty("p3", p.id, "reject")
        d = room.to_dict("p2")  # penalizer, not chairman
        assert d["pending_judge_ruling"] is None

    def test_pending_vote_shown_to_eligible_voter(self):
        room = start_room("Alice", "Bob", "Charlie")
        room.chairman_id = "p1"
        room.add_initial_rules(["No talking"], "p1")
        rule_id = next(iter(room.rules))
        p = room.issue_penalty("p1", "p2", rule_id)
        room.respond_penalty("p2", p.id, "reject")
        d = room.to_dict("p3")
        assert d["pending_vote"] is not None
        assert d["pending_vote"]["id"] == p.id

    def test_pending_vote_hidden_from_penalizer(self):
        room = start_room("Alice", "Bob", "Charlie")
        room.chairman_id = "p1"
        room.add_initial_rules(["No talking"], "p1")
        rule_id = next(iter(room.rules))
        p = room.issue_penalty("p1", "p2", rule_id)
        room.respond_penalty("p2", p.id, "reject")
        d = room.to_dict("p1")
        assert d["pending_vote"] is None

    def test_active_vote_tally_mid_vote(self):
        room = start_room("Alice", "Bob", "Charlie", "Dave")
        room.chairman_id = "p1"
        room.add_initial_rules(["No talking"], "p1")
        rule_id = next(iter(room.rules))
        p = room.issue_penalty("p1", "p2", rule_id)
        room.respond_penalty("p2", p.id, "reject")
        room.vote_penalty("p3", p.id, "uphold")
        # p4 hasn't voted yet; penalty still under_review
        assert p.status == "under_review"
        for viewer in ["p1", "p2", "p3", "p4"]:
            d = room.to_dict(viewer)
            tally = d["active_vote_tally"]
            assert tally is not None
            assert tally["uphold"] == 1
            assert tally["total_eligible"] == 2
            assert tally["total_voted"] == 1

    def test_penalties_list_in_state(self):
        room, rule_id = _room_with_penalty_setup("Alice", "Bob")
        p = room.issue_penalty("p1", "p2", rule_id)
        room.respond_penalty("p2", p.id, "accept")
        d = room.to_dict("p1")
        assert len(d["penalties"]) == 1
        assert d["penalties"][0]["status"] == "accepted"

    def test_penalties_list_capped_at_50(self):
        room = start_room("Alice", "Bob", deck_count=2)
        room.chairman_id = "p1"
        room.add_initial_rules(["No talking"], "p1")
        rule_id = next(iter(room.rules))
        for _ in range(55):
            room.issue_penalty("p1", "p2", rule_id)
        d = room.to_dict("p1")
        assert len(d["penalties"]) == 50
