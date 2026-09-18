"""Core rules for the two-player Hungarian version of Casino."""

from dataclasses import dataclass, field
from itertools import combinations


RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
_VALUES = {rank: index for index, rank in enumerate(RANKS, start=1)}


def value(card: str) -> int:
    """Return the numeric value of a card."""
    return _VALUES[card[:-1]]


@dataclass(frozen=True)
class Move:
    hand: frozenset[str]
    table: frozenset[str]


@dataclass(frozen=True)
class State:
    hands: tuple[tuple[str, ...], tuple[str, ...]]
    table: tuple[str, ...]
    talon: tuple[str, ...]
    piles: tuple[tuple[str, ...], tuple[str, ...]]
    sweeps: tuple[int, int]
    player: int
    _extra_turn: int | None = field(default=None, repr=False, compare=False)
    _last_capturer: int | None = field(default=None, repr=False, compare=False)


def new_deal(deck, first: int = 0) -> State:
    """Deal three cards to each player and four cards to the table."""
    cards = tuple(deck)
    if first not in (0, 1):
        raise ValueError("first must be 0 or 1")
    hands = [(), ()]
    hands[first] = cards[:3]
    hands[1 - first] = cards[3:6]
    return State(
        hands=(hands[0], hands[1]),
        table=cards[6:10],
        talon=cards[10:],
        piles=((), ()),
        sweeps=(0, 0),
        player=first,
    )


def _subsets(cards: tuple[str, ...], nonempty: bool = True):
    start = 1 if nonempty else 0
    for size in range(start, len(cards) + 1):
        for subset in combinations(cards, size):
            yield frozenset(subset)


def legal_moves(state: State) -> set[Move]:
    """Return every capture and placement available to the current player."""
    hand = state.hands[state.player]
    moves = {Move(frozenset({card}), frozenset()) for card in hand}
    table_subsets = list(_subsets(state.table))
    for hand_subset in _subsets(hand):
        hand_total = sum(value(card) for card in hand_subset)
        for table_subset in table_subsets:
            if sum(value(card) for card in table_subset) == hand_total:
                moves.add(Move(hand_subset, table_subset))
    return moves


def _deal_next_round(hands, talon):
    if not talon:
        return hands, talon
    cards_for_first = min(3, len(talon))
    first_cards = tuple(talon[:cards_for_first])
    remaining = talon[cards_for_first:]
    cards_for_second = min(3, len(remaining))
    second_cards = tuple(remaining[:cards_for_second])
    return [first_cards, second_cards], remaining[cards_for_second:]


def play(state: State, move: Move) -> State:
    """Apply a legal move and all automatic deal transitions."""
    if move not in legal_moves(state):
        raise ValueError("illegal move")

    player = state.player
    hands = [list(cards) for cards in state.hands]
    table = list(state.table)
    piles = [list(cards) for cards in state.piles]
    sweeps = list(state.sweeps)
    for card in move.hand:
        hands[player].remove(card)

    captured = bool(move.table)
    if captured:
        for card in move.table:
            table.remove(card)
        piles[player].extend(move.hand)
        piles[player].extend(move.table)
        if not table:
            sweeps[player] += 1
    else:
        table.extend(move.hand)

    extra_turn = state._extra_turn
    last_capturer = state._last_capturer
    if captured:
        last_capturer = player
    if not table and captured:
        extra_turn = 1 - player

    if extra_turn == player:
        next_player = player
        extra_turn = None
    else:
        next_player = 1 - player

    talon = list(state.talon)
    if not hands[0] and not hands[1] and talon:
        hands, talon = _deal_next_round(hands, talon)
        next_player = player

    if (hands[0] or hands[1]) and not hands[next_player]:
        next_player = 1 - next_player

    if not hands[0] and not hands[1] and not talon and table:
        recipient = last_capturer if last_capturer is not None else player
        piles[recipient].extend(table)
        table = []

    return State(
        hands=(tuple(hands[0]), tuple(hands[1])),
        table=tuple(table),
        talon=tuple(talon),
        piles=(tuple(piles[0]), tuple(piles[1])),
        sweeps=(sweeps[0], sweeps[1]),
        player=next_player,
        _extra_turn=extra_turn,
        _last_capturer=last_capturer,
    )


def deal_over(state: State) -> bool:
    return not state.hands[0] and not state.hands[1] and not state.talon and not state.table


def score(state: State) -> tuple[int, int]:
    points = []
    for player in (0, 1):
        pile = state.piles[player]
        points.append(
            (3 if len(pile) >= 27 else 0)
            + (2 if sum(card.endswith("S") for card in pile) >= 7 else 0)
            + sum(card.startswith("A") for card in pile)
            + (2 if "10D" in pile else 0)
            + (1 if "2S" in pile else 0)
            + state.sweeps[player]
        )
    return tuple(points)


__all__ = ["Move", "State", "deal_over", "legal_moves", "new_deal", "play", "score", "value"]