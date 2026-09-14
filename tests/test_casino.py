"""Tests for the casino module.

Cards are strings: rank, then suit.
Ranks: A 2 3 4 5 6 7 8 9 10 J Q K. Suits: S H D C.
"""
import random

import pytest

from casino import Move, deal_over, legal_moves, new_deal, play, score, value

RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
ALL = [r + s for s in "SHDC" for r in RANKS]


def deck(*front):
    """A full deck: these cards first, then the rest in a fixed order."""
    return list(front) + [c for c in ALL if c not in front]


def take(hand, table=()):
    return Move(frozenset(hand), frozenset(table))


def put(card):
    return Move(frozenset({card}), frozenset())


# --- cards and the deal -----------------------------------------------------

def test_card_values():
    assert [value(r + "H") for r in RANKS] == list(range(1, 14))


def test_new_deal():
    d = deck("AS", "2S", "3S", "4S", "5S", "6S", "7S", "8S", "9S", "10S")
    s = new_deal(d)
    assert s.hands == (("AS", "2S", "3S"), ("4S", "5S", "6S"))
    assert s.table == ("7S", "8S", "9S", "10S")
    assert s.talon == tuple(d[10:])
    assert s.piles == ((), ())
    assert s.sweeps == (0, 0)
    assert s.player == 0


def test_new_deal_other_player_first():
    d = deck("AS", "2S", "3S", "4S", "5S", "6S", "7S", "8S", "9S", "10S")
    s = new_deal(d, first=1)
    assert s.hands == (("4S", "5S", "6S"), ("AS", "2S", "3S"))
    assert s.player == 1


# --- capturing and placing --------------------------------------------------

BASIC = deck("5H", "KH", "AH", "3D", "6D", "8D", "5C", "4C", "9C", "2C")


def test_capture_a_matching_card():
    s = play(new_deal(BASIC), take({"5H"}, {"5C"}))
    assert s.hands[0] == ("KH", "AH")
    assert set(s.table) == {"4C", "9C", "2C"}
    assert set(s.piles[0]) == {"5H", "5C"}


def test_capture_a_combination_from_the_table():
    s = play(new_deal(BASIC), take({"KH"}, {"4C", "9C"}))
    assert set(s.table) == {"5C", "2C"}
    assert set(s.piles[0]) == {"KH", "4C", "9C"}


def test_capture_with_a_combination_from_hand():
    s = play(new_deal(BASIC), take({"5H", "AH"}, {"4C", "2C"}))
    assert s.hands[0] == ("KH",)
    assert set(s.table) == {"5C", "9C"}


def test_legal_moves_include_captures_and_places():
    moves = legal_moves(new_deal(BASIC))
    assert take({"5H"}, {"5C"}) in moves
    assert take({"KH"}, {"4C", "9C"}) in moves
    assert take({"5H", "AH"}, {"4C", "2C"}) in moves
    assert put("AH") in moves


def test_place_a_card():
    s = play(new_deal(BASIC), put("AH"))
    assert s.hands[0] == ("5H", "KH")
    assert set(s.table) == {"5C", "4C", "9C", "2C", "AH"}
    assert s.piles == ((), ())


def test_capture_must_add_up():
    with pytest.raises(ValueError):
        play(new_deal(BASIC), take({"5H"}, {"4C"}))


def test_cannot_play_a_card_you_do_not_hold():
    with pytest.raises(ValueError):
        play(new_deal(BASIC), put("3D"))


def test_players_take_turns():
    s = play(new_deal(BASIC), put("AH"))
    assert s.player == 1
    s = play(s, put("3D"))
    assert s.player == 0


# --- sweeps and rounds ------------------------------------------------------

SWEEP = deck("4H", "7H", "QH", "AD", "5D", "9D", "AC", "2C", "3C", "4C")


def test_sweep_and_the_double_move_after_it():
    s = play(new_deal(SWEEP), take({"4H"}, {"4C"}))
    s = play(s, put("AD"))
    s = play(s, take({"7H"}, {"AC", "2C", "3C", "AD"}))
    assert s.table == ()
    assert s.sweeps == (1, 0)
    assert s.player == 1
    assert all(not m.table for m in legal_moves(s))
    s = play(s, put("5D"))
    assert s.player == 1
    s = play(s, put("9D"))
    assert s.player == 0


def test_new_round_last_capturer_draws_and_leads():
    s = play(new_deal(SWEEP), take({"4H"}, {"4C"}))
    s = play(s, put("AD"))
    s = play(s, take({"7H"}, {"AC", "2C", "3C", "AD"}))
    s = play(s, put("5D"))
    s = play(s, put("9D"))
    talon = s.talon
    s = play(s, put("QH"))
    assert s.hands == (talon[0:3], talon[3:6])
    assert s.talon == talon[6:]
    assert set(s.table) == {"5D", "9D", "QH"}
    assert s.player == 0


# --- a whole deal -----------------------------------------------------------

def choose(s):
    """A fixed way of choosing a move, so that a whole deal can be played."""
    moves = legal_moves(s)
    left = len(s.hands[0]) + len(s.hands[1]) + len(s.talon)
    captures = [m for m in moves if m.table]
    if captures and left > 1:
        return max(captures, key=lambda m: (len(m.table), sorted(m.table), sorted(m.hand)))
    return min((m for m in moves if not m.table), key=lambda m: sorted(m.hand))


def play_whole_deal(seed):
    cards = list(ALL)
    random.Random(seed).shuffle(cards)
    s, last_capturer = new_deal(cards), None
    for _ in range(200):
        if deal_over(s):
            break
        before, move = s, choose(s)
        if move.table:
            last_capturer = s.player
        s = play(s, move)
    return before, move, s, last_capturer


def expected_score(s):
    points = []
    for p in (0, 1):
        pile = s.piles[p]
        points.append((3 if len(pile) >= 27 else 0)
                      + (2 if sum(c.endswith("S") for c in pile) >= 7 else 0)
                      + sum(c.startswith("A") for c in pile)
                      + (2 if "10D" in pile else 0)
                      + (1 if "2S" in pile else 0)
                      + s.sweeps[p])
    return tuple(points)


def test_a_whole_deal():
    before, move, s, last_capturer = play_whole_deal(2026)
    assert deal_over(s)
    assert sorted(s.piles[0] + s.piles[1]) == sorted(ALL)
    leftover = set(before.table) | set(move.hand)
    assert leftover <= set(s.piles[last_capturer])
    assert score(s) == expected_score(s)
