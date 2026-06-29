import { useState, useRef, useEffect, useCallback } from "react";
import "./App.css";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const WS_URL = API.replace(/^http/, "ws") + "/ws";

const SUIT_SYMBOL = { hearts: "♥", diamonds: "♦", clubs: "♣", spades: "♠" };
const isRed = (suit) => suit === "hearts" || suit === "diamonds";

// ---------------------------------------------------------------------------
// PlayingCard
// ---------------------------------------------------------------------------

function PlayingCard({ rank, suit, onClick, large = false }) {
  const playable = typeof onClick === "function";
  return (
    <button
      type="button"
      className={[
        "card",
        isRed(suit) ? "red" : "black",
        playable ? "playable" : "",
        large ? "card-lg" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      onClick={playable ? onClick : undefined}
      disabled={!playable}
      aria-label={`${rank} of ${suit}`}
    >
      <span className="card-rank">{rank}</span>
      <span className="card-suit">{SUIT_SYMBOL[suit] ?? suit}</span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// ChatPanel
// ---------------------------------------------------------------------------

function ChatPanel({ messages, onSend }) {
  const [text, setText] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setText("");
  };

  const fmt = (iso) => {
    try {
      return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  };

  return (
    <div className="chat-panel">
      <div className="chat-header">Chat</div>
      <div className="chat-messages">
        {messages.length === 0 && <p className="chat-empty">No messages yet.</p>}
        {messages.map((m, i) => (
          <div key={i} className="chat-msg">
            <span className="chat-from">{m.from}</span>
            {m.timestamp && <span className="chat-time">{fmt(m.timestamp)}</span>}
            <div className="chat-text">{m.text}</div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <form className="chat-input-row" onSubmit={handleSubmit}>
        <input
          className="chat-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Say something…"
          maxLength={200}
        />
        <button type="submit" className="btn btn-primary btn-sm" disabled={!text.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// RulesPanel (lobby)
// ---------------------------------------------------------------------------

function RulesPanel({ rules, isChairman, onProposeRule, onReviewRule }) {
  const [ruleInput, setRuleInput] = useState("");

  const activeRules = rules.filter((r) => r.status === "active");
  const pendingRules = rules.filter((r) => r.status === "pending_approval");

  const handlePropose = (e) => {
    e.preventDefault();
    const name = ruleInput.trim();
    if (!name) return;
    onProposeRule(name);
    setRuleInput("");
  };

  return (
    <div className="rules-panel">
      <h2>Rules</h2>

      <div className="rules-section">
        <div className="rules-section-label">Active</div>
        {activeRules.length === 0 ? (
          <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>No active rules yet.</p>
        ) : (
          <ul className="rules-list">
            {activeRules.map((r) => (
              <li key={r.id} className="rule-item">
                <span>{r.name}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {pendingRules.length > 0 && (
        <div className="rules-section">
          <div className="rules-section-label">Pending</div>
          <ul className="rules-list">
            {pendingRules.map((r) => (
              <li key={r.id} className="rule-item rule-item-pending">
                <div className="rule-item-main">
                  <span className="rule-name">{r.name}</span>
                  <span className="rule-proposer">by {r.proposed_by}</span>
                </div>
                {isChairman ? (
                  <div className="rule-actions">
                    <button type="button" className="btn btn-win btn-sm" onClick={() => onReviewRule(r.id, "approve")}>Approve</button>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => onReviewRule(r.id, "reject")}>Reject</button>
                  </div>
                ) : (
                  <span className="badge badge-warn" style={{ marginLeft: "auto" }}>pending chairman</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <form className="rule-input-row" onSubmit={handlePropose}>
        <input
          className="rule-input"
          value={ruleInput}
          onChange={(e) => setRuleInput(e.target.value)}
          placeholder="Propose a rule name…"
          maxLength={100}
        />
        <button type="submit" className="btn btn-secondary btn-sm" disabled={!ruleInput.trim()}>
          Propose
        </button>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PenalizeModal
// ---------------------------------------------------------------------------

function PenalizeModal({ players, playerName, rules, onSubmit, onClose }) {
  const activeRules = rules.filter((r) => r.status === "active");
  const targets = Object.values(players).filter((p) => p.id !== playerName);

  const [targetId, setTargetId] = useState(targets[0]?.id ?? "");
  const [ruleId, setRuleId] = useState(activeRules[0]?.id ?? "");
  const [cards, setCards] = useState(1);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!targetId || !ruleId) return;
    onSubmit(targetId, ruleId, cards);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">Issue Penalty</span>
          <button type="button" className="btn-close" onClick={onClose}>×</button>
        </div>
        <p className="modal-note">
          The target receives the card(s) immediately, then may accept or contest.
        </p>
        <form onSubmit={handleSubmit} className="form-stack">
          <label>
            Target player
            <select value={targetId} onChange={(e) => setTargetId(e.target.value)} className="form-select">
              {targets.length === 0
                ? <option value="">No other players</option>
                : targets.map((p) => (
                    <option key={p.id} value={p.id}>{p.display_name}</option>
                  ))}
            </select>
          </label>
          <label>
            Rule violated
            <select value={ruleId} onChange={(e) => setRuleId(e.target.value)} className="form-select">
              {activeRules.length === 0
                ? <option value="">No active rules</option>
                : activeRules.map((r) => (
                    <option key={r.id} value={r.id}>{r.name}</option>
                  ))}
            </select>
          </label>
          <label>
            Cards to give
            <input
              type="number"
              min={1}
              max={10}
              value={cards}
              onChange={(e) => setCards(Math.max(1, Number(e.target.value)))}
            />
          </label>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={!targetId || activeRules.length === 0}
            >
              Issue Penalty
            </button>
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PenaltyResponseBanner  (shown to the target)
// ---------------------------------------------------------------------------

function PenaltyResponseBanner({ penalty, players, onRespond }) {
  const fromName = players[penalty.from_player]?.display_name ?? penalty.from_player;
  return (
    <div className="penalty-banner penalty-banner-target">
      <div className="penalty-banner-title">You received a penalty!</div>
      <p className="penalty-banner-body">
        <strong>{fromName}</strong> cited rule <em>"{penalty.rule_name}"</em> —{" "}
        <strong>{penalty.cards} card{penalty.cards !== 1 ? "s" : ""}</strong> added to your hand.
      </p>
      <div className="penalty-banner-actions">
        <button type="button" className="btn btn-win btn-sm" onClick={() => onRespond(penalty.id, "accept")}>
          Accept Penalty
        </button>
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => onRespond(penalty.id, "reject")}>
          Contest It
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// JudgeRulingBanner  (shown to the chairman when they must rule)
// ---------------------------------------------------------------------------

function JudgeRulingBanner({ penalty, players, onJudge }) {
  const fromName = players[penalty.from_player]?.display_name ?? penalty.from_player;
  const toName = players[penalty.to_player]?.display_name ?? penalty.to_player;
  return (
    <div className="penalty-banner penalty-banner-judge">
      <div className="penalty-banner-title">Chairman ruling required</div>
      <p className="penalty-banner-body">
        <strong>{fromName}</strong> penalized <strong>{toName}</strong> for{" "}
        <em>"{penalty.rule_name}"</em> ({penalty.cards} card{penalty.cards !== 1 ? "s" : ""}).{" "}
        The target contested it.
      </p>
      <div className="penalty-banner-actions">
        <button type="button" className="btn btn-primary btn-sm" onClick={() => onJudge(penalty.id, "uphold")}>
          Uphold
        </button>
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => onJudge(penalty.id, "overturn")}>
          Overturn
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// VoteBanner  (shown to each eligible voter)
// ---------------------------------------------------------------------------

function VoteBanner({ penalty, players, onVote }) {
  const fromName = players[penalty.from_player]?.display_name ?? penalty.from_player;
  const toName = players[penalty.to_player]?.display_name ?? penalty.to_player;
  return (
    <div className="penalty-banner penalty-banner-vote">
      <div className="penalty-banner-title">Popular vote — your input needed</div>
      <p className="penalty-banner-body">
        <strong>{fromName}</strong> (Chairman) penalized <strong>{toName}</strong> for{" "}
        <em>"{penalty.rule_name}"</em>. The target contested it.
      </p>
      <div className="penalty-banner-actions">
        <button type="button" className="btn btn-primary btn-sm" onClick={() => onVote(penalty.id, "uphold")}>
          Uphold Penalty
        </button>
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => onVote(penalty.id, "overturn")}>
          Overturn Penalty
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// VoteTallyBar  (visible to everyone during a popular vote)
// ---------------------------------------------------------------------------

function VoteTallyBar({ tally }) {
  const { uphold, overturn, total_eligible, total_voted, rule_name, from_player, to_player } = tally;
  return (
    <div className="vote-tally-bar">
      <span className="vote-tally-label">
        Vote: <strong>{from_player}</strong> vs <strong>{to_player}</strong>{" "}
        · <em>{rule_name}</em>
      </span>
      <span className="vote-tally-counts">
        <span className="vote-uphold">{uphold} uphold</span>
        {" · "}
        <span className="vote-overturn">{overturn} overturn</span>
        {" · "}
        <span className="vote-progress">{total_voted}/{total_eligible} voted</span>
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PenaltyLog  (sidebar tab)
// ---------------------------------------------------------------------------

function PenaltyLog({ penalties }) {
  if (!penalties || penalties.length === 0) {
    return <p className="chat-empty" style={{ padding: "12px 14px" }}>No penalties yet.</p>;
  }
  const reversed = [...penalties].reverse();
  return (
    <div className="penalty-log">
      {reversed.map((p) => (
        <div key={p.id} className={`penalty-entry penalty-status-${p.status}`}>
          <div className="penalty-entry-header">
            <span className="penalty-from">{p.from_player}</span>
            <span className="penalty-arrow">→</span>
            <span className="penalty-to">{p.to_player}</span>
            <span className={`penalty-status-badge status-${p.status}`}>{p.status}</span>
          </div>
          <div className="penalty-rule-name">"{p.rule_name}" · {p.cards}×</div>
          {p.log.map((entry, i) => (
            <div key={i} className="penalty-log-line">{entry}</div>
          ))}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// TableSidebar  (chat / penalty log tabs)
// ---------------------------------------------------------------------------

function TableSidebar({ chatMessages, onChatSend, penalties }) {
  const [tab, setTab] = useState("chat");
  const unresolved = penalties.filter(
    (p) => p.status !== "accepted" && p.status !== "upheld" && p.status !== "overturned"
  ).length;

  return (
    <div className="table-chat">
      <div className="sidebar-tabs">
        <button
          type="button"
          className={`sidebar-tab ${tab === "chat" ? "active" : ""}`}
          onClick={() => setTab("chat")}
        >
          Chat
        </button>
        <button
          type="button"
          className={`sidebar-tab ${tab === "log" ? "active" : ""}`}
          onClick={() => setTab("log")}
        >
          Penalties{penalties.length > 0 ? ` (${penalties.length})` : ""}
          {unresolved > 0 && <span className="sidebar-tab-dot" />}
        </button>
      </div>
      {tab === "chat" ? (
        <ChatPanel messages={chatMessages} onSend={onChatSend} />
      ) : (
        <PenaltyLog penalties={penalties} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// LandingScreen
// ---------------------------------------------------------------------------

function LandingScreen({ onCreateRoom, onJoinRoom, error }) {
  const [createName, setCreateName] = useState("");
  const [deckCount, setDeckCount] = useState(1);
  const [joinName, setJoinName] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [creating, setCreating] = useState(false);
  const [initialRules, setInitialRules] = useState([]);
  const [ruleInput, setRuleInput] = useState("");

  const addRule = () => {
    const name = ruleInput.trim();
    if (!name) return;
    setInitialRules((prev) => [...prev, name]);
    setRuleInput("");
  };

  const removeRule = (i) => setInitialRules((prev) => prev.filter((_, idx) => idx !== i));

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!createName.trim()) return;
    setCreating(true);
    try {
      await onCreateRoom({ name: createName.trim(), deckCount, initialRules });
    } finally {
      setCreating(false);
    }
  };

  const handleJoin = (e) => {
    e.preventDefault();
    if (!joinName.trim() || !joinCode.trim()) return;
    onJoinRoom({ name: joinName.trim(), code: joinCode.trim().toUpperCase() });
  };

  return (
    <div className="landing">
      <h1 className="site-logo">Online Mao</h1>
      {error && <div className="error-banner">{error}</div>}
      <div className="landing-panels">
        <div className="panel">
          <h2>Create Room</h2>
          <form onSubmit={handleCreate} className="form-stack">
            <label>
              Your name
              <input value={createName} onChange={(e) => setCreateName(e.target.value)} placeholder="Enter your name" autoFocus required />
            </label>
            <label>
              Number of decks
              <input type="number" min={1} max={4} value={deckCount} onChange={(e) => setDeckCount(Number(e.target.value))} />
            </label>
            <div>
              <div className="form-sublabel">Initial rules (optional)</div>
              <div className="rule-input-row" style={{ marginTop: 5 }}>
                <input
                  className="rule-input"
                  value={ruleInput}
                  onChange={(e) => setRuleInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addRule(); } }}
                  placeholder="Add a rule name…"
                  maxLength={100}
                />
                <button type="button" className="btn btn-ghost btn-sm" onClick={addRule} disabled={!ruleInput.trim()}>Add</button>
              </div>
              {initialRules.length > 0 && (
                <div className="initial-rules-list">
                  {initialRules.map((rule, i) => (
                    <div key={i} className="rule-tag">
                      <span>{rule}</span>
                      <button type="button" className="rule-tag-remove" onClick={() => removeRule(i)} aria-label={`Remove "${rule}"`}>×</button>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <button type="submit" className="btn btn-primary" disabled={creating}>
              {creating ? "Creating…" : "Create Room →"}
            </button>
          </form>
        </div>

        <div className="panel-divider" aria-hidden="true" />

        <div className="panel">
          <h2>Join Room</h2>
          <form onSubmit={handleJoin} className="form-stack">
            <label>
              Your name
              <input value={joinName} onChange={(e) => setJoinName(e.target.value)} placeholder="Enter your name" required />
            </label>
            <label>
              Room code
              <input value={joinCode} onChange={(e) => setJoinCode(e.target.value.toUpperCase())} placeholder="e.g. A3F7" maxLength={4} required />
            </label>
            <button type="submit" className="btn btn-secondary">Join Room →</button>
          </form>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// LobbyScreen
// ---------------------------------------------------------------------------

function LobbyScreen({ roomCode, playerName, isChairman, gameState, onStart, deckCount, chatMessages, onChatSend, onProposeRule, onReviewRule, onTransferChairman }) {
  const players = gameState ? Object.values(gameState.players) : [];
  const rules = gameState?.rules ?? [];
  const chairmanId = gameState?.chairman_id ?? null;
  const canStart = isChairman && players.length >= 2;

  const copyCode = () => navigator.clipboard?.writeText(roomCode).catch(() => {});

  return (
    <div className="lobby">
      <h1 className="site-logo">Online Mao</h1>

      <div className="room-code-box">
        <span className="room-code-label">Room Code</span>
        <span className="room-code-value">{roomCode}</span>
        <button type="button" className="btn btn-ghost btn-sm" onClick={copyCode}>Copy</button>
      </div>

      <div className="player-list-box">
        <h2>Players</h2>
        {players.length === 0 ? (
          <p className="muted">Waiting for players to join…</p>
        ) : (
          <ul className="player-list">
            {players.map((p) => (
              <li key={p.id} className={["player-item", p.id === playerName ? "is-you" : "", !p.connected ? "is-disconnected" : ""].filter(Boolean).join(" ")}>
                {p.id === chairmanId && <span className="badge badge-chairman">Chairman</span>}
                <span style={{ flex: 1 }}>{p.display_name}</span>
                {p.id === playerName && <span className="badge badge-you">you</span>}
                {!p.connected && <span className="badge badge-warn">disconnected</span>}
                {isChairman && p.id !== playerName && p.connected && (
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => onTransferChairman(p.id)}>Make Chairman</button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <RulesPanel rules={rules} isChairman={isChairman} onProposeRule={onProposeRule} onReviewRule={onReviewRule} />

      {isChairman ? (
        <div className="lobby-actions">
          {players.length < 2 && <p className="muted">Need at least 2 players to start.</p>}
          <p className="muted" style={{ fontSize: 13 }}>{deckCount} deck{deckCount !== 1 ? "s" : ""} · 7 cards per player</p>
          <button type="button" className="btn btn-primary btn-lg" disabled={!canStart} onClick={onStart}>Start Game</button>
        </div>
      ) : (
        <p className="muted">Waiting for the chairman to start the game…</p>
      )}

      <div className="lobby-chat">
        <ChatPanel messages={chatMessages} onSend={onChatSend} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// TableScreen
// ---------------------------------------------------------------------------

function TableScreen({ gameState, playerName, onSend, actionError, onClearError, chatMessages, onChatSend }) {
  const [showPenalizeModal, setShowPenalizeModal] = useState(false);

  if (!gameState) return <div className="fullscreen-center">Connecting…</div>;

  const {
    state, player_order, current_turn_index, top_card, players, room_id, direction, winner,
    chairman_id, rules = [], penalties = [],
    pending_penalty_response, pending_judge_ruling, pending_vote, active_vote_tally,
  } = gameState;

  const currentTurnId = player_order[current_turn_index];
  const isMyTurn = currentTurnId === playerName;
  const finished = state === "finished";
  const me = players[playerName] ?? {};
  const myHand = me.hand ?? [];
  const winnerName = winner ? (players[winner]?.display_name ?? winner) : null;
  const otherPlayers = player_order.filter((id) => id !== playerName);
  const activeRules = rules.filter((r) => r.status === "active");

  const sendClear = useCallback((msg) => { onClearError(); onSend(msg); }, [onSend, onClearError]);

  const penalize    = (tId, rId, c)  => onSend({ type: "penalize",        target_player_id: tId, rule_id: rId, cards: c });
  const respondP    = (pId, resp)     => onSend({ type: "respond_penalty", penalty_id: pId, response: resp });
  const judgeP      = (pId, ruling)   => onSend({ type: "judge_penalty",   penalty_id: pId, ruling });
  const voteP       = (pId, vote)     => onSend({ type: "vote_penalty",    penalty_id: pId, vote });

  const hasPenaltyAction = pending_penalty_response || pending_judge_ruling || pending_vote;

  return (
    <div className="table-screen">
      {/* ── Header ── */}
      <header className="table-header">
        <span className="room-tag">{room_id} · {direction === 1 ? "CW ↻" : "CCW ↺"}</span>
        <span className={`turn-label ${isMyTurn && !finished ? "my-turn" : ""}`}>
          {finished
            ? `${winnerName === me.display_name ? "You" : winnerName} won!`
            : isMyTurn
            ? "Your turn!"
            : `${players[currentTurnId]?.display_name ?? currentTurnId}'s turn`}
        </span>
        <span className="hand-count-badge">{myHand.length} card{myHand.length !== 1 ? "s" : ""}</span>
      </header>

      <div className="table-body">
        <div className="table-main">

          {/* ── Game arena: opponents arc + green felt oval ── */}
          <div className="game-arena">

            <div className={`opponents-arc opp-n-${otherPlayers.length}`}>
              {otherPlayers.length === 0 ? (
                <span className="muted" style={{ fontSize: 13 }}>Waiting for other players…</span>
              ) : (
                otherPlayers.map((pid) => {
                  const p = players[pid] ?? {};
                  const isActive = pid === currentTurnId && !finished;
                  const handSize = p.hand_size ?? 0;
                  return (
                    <div
                      key={pid}
                      className={[
                        "opponent-seat",
                        isActive ? "active" : "",
                        !p.connected ? "disconnected" : "",
                      ].filter(Boolean).join(" ")}
                    >
                      <div className="opp-meta">
                        {pid === chairman_id && <span className="opp-crown" title="Chairman">♛</span>}
                        <span className="opp-name">{p.display_name}</span>
                        {!p.connected && <span className="opp-dc-icon">⚠</span>}
                      </div>
                      <div className="opp-card-backs" title={`${handSize} card${handSize !== 1 ? "s" : ""}`}>
                        {handSize === 0
                          ? <span className="opp-empty-label">empty</span>
                          : <>
                              {Array.from({ length: Math.min(handSize, 7) }).map((_, j) => (
                                <div key={j} className="card-back-mini" />
                              ))}
                              {handSize > 7 && <span className="opp-extra-count">+{handSize - 7}</span>}
                            </>
                        }
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* The felt table with discard pile */}
            <div className="table-felt">
              <span className="felt-label">top card</span>
              {top_card
                ? <PlayingCard large rank={top_card.rank} suit={top_card.suit} />
                : <div className="card card-empty card-lg" aria-label="No card yet">—</div>
              }
            </div>

          </div>

          {/* ── Penalty banners ── */}
          {hasPenaltyAction && (
            <div className="penalty-banners">
              {pending_penalty_response && (
                <PenaltyResponseBanner penalty={pending_penalty_response} players={players} onRespond={respondP} />
              )}
              {pending_judge_ruling && (
                <JudgeRulingBanner penalty={pending_judge_ruling} players={players} onJudge={judgeP} />
              )}
              {pending_vote && (
                <VoteBanner penalty={pending_vote} players={players} onVote={voteP} />
              )}
            </div>
          )}

          {active_vote_tally && <VoteTallyBar tally={active_vote_tally} />}

          {/* ── Your fanned hand ── */}
          <section
            className={`hand-section ${isMyTurn && !finished ? "hand-my-turn" : ""}`}
            aria-label="Your hand"
          >
            <div className="hand-label-row">
              <span className="area-label">your hand</span>
              {isMyTurn && !finished && <span className="your-turn-tag">YOUR TURN</span>}
            </div>
            <div className="hand-fan">
              {myHand.length === 0 && !finished ? (
                <span className="muted" style={{ fontSize: 14 }}>Your hand is empty!</span>
              ) : (
                myHand.map((card, i) => {
                  const total = myHand.length;
                  const mid   = (total - 1) / 2;
                  const off   = i - mid;
                  const ang   = off * Math.min(5, 44 / Math.max(total, 1));
                  const yLift = Math.abs(off) * Math.min(4, 28 / Math.max(total, 1));
                  return (
                    <div
                      key={`${card.rank}-${card.suit}-${i}`}
                      className={`card-fan-slot ${isMyTurn && !finished ? "playable-slot" : ""}`}
                      style={{ "--fan-angle": `${ang}deg`, "--fan-y": `${yLift}px`, zIndex: i }}
                    >
                      <PlayingCard
                        rank={card.rank}
                        suit={card.suit}
                        onClick={isMyTurn && !finished ? () => sendClear({ type: "play_card", card }) : undefined}
                      />
                    </div>
                  );
                })
              )}
            </div>
          </section>

          {/* ── Action bar ── */}
          <div className="action-bar">
            <button
              type="button"
              className="btn btn-secondary"
              disabled={!isMyTurn || finished}
              onClick={() => sendClear({ type: "draw_card" })}
            >
              Draw Card
            </button>
            {!finished && (
              <button
                type="button"
                className="btn btn-penalty"
                onClick={() => setShowPenalizeModal(true)}
                disabled={activeRules.length === 0}
                title={activeRules.length === 0 ? "No active rules to cite" : "Issue a penalty"}
              >
                Penalize
              </button>
            )}
          </div>

          {actionError && (
            <div className="action-error" role="alert">
              <span>{actionError}</span>
              <button type="button" className="btn-close" onClick={onClearError} aria-label="Dismiss">×</button>
            </div>
          )}

        </div>

        <TableSidebar chatMessages={chatMessages} onChatSend={onChatSend} penalties={penalties} />
      </div>

      {finished && (
        <div className="win-overlay" role="status">
          <div className="win-card">
            {winnerName === me.display_name ? "You won — Mao!" : `${winnerName} wins — Mao!`}
          </div>
        </div>
      )}

      {showPenalizeModal && (
        <PenalizeModal
          players={players}
          playerName={playerName}
          rules={rules}
          onSubmit={penalize}
          onClose={() => setShowPenalizeModal(false)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// App (root)
// ---------------------------------------------------------------------------

export default function App() {
  const [screen, setScreen] = useState("landing");
  const [playerName, setPlayerName] = useState("");
  const [roomCode, setRoomCode] = useState("");
  const [chairmanToken, setChairmanToken] = useState(null);
  const [deckCount, setDeckCount] = useState(1);
  const [gameState, setGameState] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [connError, setConnError] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);

  const wsRef = useRef(null);
  const hasJoinedRef = useRef(false);
  const pendingErrRef = useRef(null);

  const send = useCallback((msg) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  const sendChat = useCallback((text) => send({ type: "chat_message", text }), [send]);

  const connectWs = useCallback((code, name, token = null) => {
    wsRef.current?.close();
    hasJoinedRef.current = false;
    pendingErrRef.current = null;
    setChatMessages([]);

    const url = token
      ? `${WS_URL}/${code}/${name}?chairman_token=${token}`
      : `${WS_URL}/${code}/${name}`;
    const ws = new WebSocket(url);

    ws.onmessage = (e) => {
      let msg;
      try { msg = JSON.parse(e.data); } catch { return; }
      if (msg.type === "state_update") {
        hasJoinedRef.current = true;
        setConnError(null);
        setGameState(msg.state);
        setScreen(msg.state.state === "waiting" ? "lobby" : "table");
      } else if (msg.type === "error") {
        if (hasJoinedRef.current) setActionError(msg.message);
        else pendingErrRef.current = msg.message;
      } else if (msg.type === "chat_message") {
        setChatMessages((prev) => [...prev, msg]);
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
      if (!hasJoinedRef.current) {
        setConnError(pendingErrRef.current ?? "Could not join room.");
        setScreen("landing");
      }
      pendingErrRef.current = null;
    };

    ws.onerror = () => { pendingErrRef.current = "WebSocket error — is the server running?"; };
    wsRef.current = ws;
  }, []);

  const createRoom = useCallback(async ({ name, deckCount: dc, initialRules }) => {
    setConnError(null);
    let resp;
    try {
      resp = await fetch(`${API}/rooms`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initial_rules: initialRules ?? [] }),
      });
    } catch {
      setConnError(`Cannot reach server at ${API} — is the backend running?`);
      return;
    }
    if (!resp.ok) { setConnError("Server error creating room."); return; }
    const { room_code, chairman_token } = await resp.json();
    setPlayerName(name);
    setRoomCode(room_code);
    setChairmanToken(chairman_token);
    setDeckCount(dc);
    connectWs(room_code, name, chairman_token);
  }, [connectWs]);

  const joinRoom = useCallback(({ name, code }) => {
    setConnError(null);
    setPlayerName(name);
    setRoomCode(code);
    connectWs(code, name);
  }, [connectWs]);

  const startGame        = useCallback(() => send({ type: "start_game", deck_count: deckCount }), [send, deckCount]);
  const proposeRule      = useCallback((name) => send({ type: "propose_rule", name }), [send]);
  const reviewRule       = useCallback((rId, dec) => send({ type: "review_rule", rule_id: rId, decision: dec }), [send]);
  const transferChairman = useCallback((tId) => send({ type: "transfer_chairman", target_player_id: tId }), [send]);

  useEffect(() => () => wsRef.current?.close(), []);

  const isChairman = !!gameState && gameState.chairman_id === playerName;

  if (screen === "landing") {
    return <LandingScreen onCreateRoom={createRoom} onJoinRoom={joinRoom} error={connError} />;
  }

  if (screen === "lobby") {
    return (
      <LobbyScreen
        roomCode={roomCode}
        playerName={playerName}
        isChairman={isChairman}
        gameState={gameState}
        onStart={startGame}
        deckCount={deckCount}
        chatMessages={chatMessages}
        onChatSend={sendChat}
        onProposeRule={proposeRule}
        onReviewRule={reviewRule}
        onTransferChairman={transferChairman}
      />
    );
  }

  return (
    <TableScreen
      gameState={gameState}
      playerName={playerName}
      onSend={send}
      actionError={actionError}
      onClearError={() => setActionError(null)}
      chatMessages={chatMessages}
      onChatSend={sendChat}
    />
  );
}
