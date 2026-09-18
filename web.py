"""A dependency-free browser interface for playing a deal of Casino."""

import json
import random
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from casino import Move, deal_over, legal_moves, new_deal, play, score


RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
SUITS = "SHDC"
DECK = tuple(rank + suit for suit in SUITS for rank in RANKS)
state = None


def _serialize():
    return {
        "hands": state.hands[0],
        "table": state.table,
        "talon": len(state.talon),
        "score": score(state),
        "player": state.player,
        "over": deal_over(state),
    }


def _computer_turn():
    global state
    if state.player != 1 or deal_over(state):
        return
    moves = legal_moves(state)
    captures = [move for move in moves if move.table]
    move = max(captures, key=lambda item: (len(item.table), sorted(item.table))) if captures else next(iter(moves))
    state = play(state, move)


def _new_game():
    global state
    cards = list(DECK)
    random.shuffle(cards)
    state = new_deal(cards)


HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Casino</title><style>
:root{font-family:Georgia,serif;color:#f5edda;background:#123b35}*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(circle at 50% -10%,#27685a,#09231f 70%)}main{max-width:980px;margin:auto;padding:28px 20px 44px}header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #77a18d;padding-bottom:18px}h1{font-size:clamp(2.5rem,7vw,5rem);font-weight:400;letter-spacing:.04em;margin:0;color:#f3c969}.stats{display:flex;gap:20px;text-align:right;font:600 12px system-ui;letter-spacing:.12em;text-transform:uppercase}.felt{margin:28px 0;padding:28px 18px 36px;border:1px solid #4c8c72;border-radius:8px;background:linear-gradient(135deg,#175744,#0c382d);box-shadow:0 18px 50px #061a16}.label{font:600 11px system-ui;letter-spacing:.15em;text-transform:uppercase;color:#a9cfb6}.cards{display:flex;flex-wrap:wrap;gap:12px;min-height:126px;margin:12px 0 28px}.card{width:76px;height:108px;border:0;border-radius:6px;background:#fffaf0;color:#192b25;font:700 19px Georgia;box-shadow:0 5px 10px #061a1666;cursor:pointer;transition:transform .15s,box-shadow .15s}.card:hover{transform:translateY(-7px) rotate(-2deg);box-shadow:0 12px 16px #061a1699}.card.red{color:#aa3a35}.card.selected{outline:3px solid #f3c969;transform:translateY(-7px)}.actions{display:flex;align-items:center;gap:14px;flex-wrap:wrap}.button{border:1px solid #f3c969;border-radius:4px;padding:12px 18px;background:#f3c969;color:#173d31;font:700 13px system-ui;cursor:pointer}.button.secondary{background:transparent;color:#f3c969}.message{color:#d7e7d5;font:15px system-ui}.history{font:14px system-ui;color:#b9d9c1}footer{font:12px system-ui;color:#8fb6a0}
</style></head><body><main><header><h1>Casino</h1><div class="stats"><div>You<br><strong id="you">0</strong></div><div>Computer<br><strong id="computer">0</strong></div><div>Stock<br><strong id="stock">42</strong></div></div></header><section class="felt"><div class="label">Table</div><div id="table" class="cards"></div><div class="label">Your hand</div><div id="hand" class="cards"></div><div class="actions"><button class="button" id="play">Play selected card</button><button class="button secondary" id="new">New deal</button><span class="message" id="message"></span></div></section><div class="history" id="status"></div><footer>Choose a card, then choose any table cards it can capture. A blank selection places the card.</footer></main><script>
let selected=new Set(), tableSelected=new Set(), data;
const handEl=document.getElementById('hand'), tableEl=document.getElementById('table'), youEl=document.getElementById('you'), computerEl=document.getElementById('computer'), stockEl=document.getElementById('stock'), messageEl=document.getElementById('message'), statusEl=document.getElementById('status'), playButton=document.getElementById('play'), newButton=document.getElementById('new');
const rankValue=c=>({A:1,J:11,Q:12,K:13}[c.slice(0,-1)]||+c.slice(0,-1));
async function refresh(){data=await fetch('/state').then(r=>r.json());render()}
function card(c,zone){let b=document.createElement('button');b.className='card '+('HD'.includes(c.slice(-1))?'red':'');b.textContent=c;b.onclick=()=>{let set=zone==='hand'?selected:tableSelected;set.has(c)?set.delete(c):set.add(c);render()};if((zone==='hand'?selected:tableSelected).has(c))b.classList.add('selected');return b}
function render(){handEl.replaceChildren(...(data.hands||[]).map(c=>card(c,'hand')));tableEl.replaceChildren(...(data.table||[]).map(c=>card(c,'table')));youEl.textContent=data.score[0];computerEl.textContent=data.score[1];stockEl.textContent=data.talon;messageEl.textContent=data.over?'Deal over. Start a new deal.':data.player===0?'Your turn':'Computer is thinking...';statusEl.textContent=data.over?'Final score: '+data.score.join(' - '):'Select one card from your hand and optional cards from the table.'}
playButton.onclick=async()=>{if(!selected.size){messageEl.textContent='Select at least one card from your hand.';return}let r=await fetch('/play',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({hand:[...selected],table:[...tableSelected]})});if(!r.ok){messageEl.textContent='That capture is not legal.';return}selected.clear();tableSelected.clear();await refresh();if(data.player===1&&!data.over){await fetch('/computer',{method:'POST'});await refresh()}};newButton.onclick=async()=>{await fetch('/new',{method:'POST'});selected.clear();tableSelected.clear();refresh()};refresh();
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, content_type="application/json", status=200):
        encoded = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if urlparse(self.path).path == "/state":
            self._send(json.dumps(_serialize()))
        else:
            self._send(HTML, "text/html")

    def do_POST(self):
        global state
        path = urlparse(self.path).path
        if path == "/new":
            _new_game()
        elif path == "/computer":
            _computer_turn()
        elif path == "/play":
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length))
            try:
                state = play(state, Move(frozenset(payload["hand"]), frozenset(payload["table"])))
            except (KeyError, ValueError):
                self._send("illegal move", status=400)
                return
        self._send(json.dumps(_serialize()))


if __name__ == "__main__":
    _new_game()
    print("Casino is running at http://127.0.0.1:8000")
    HTTPServer(("127.0.0.1", 8000), Handler).serve_forever()