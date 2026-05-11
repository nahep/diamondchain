"""
DiamondChain backend
  POST /register   — register a diamond, anchor to Solana devnet via memo tx
  GET  /verify/<id> — return diamond passport JSON
  GET  /qr/<id>    — return QR code PNG

Run:
  pip install solana solders spl-token flask flask-cors qrcode[pil] anthropic
  python backend.py
"""

import json
import os
import io
import time
import hashlib
from datetime import datetime
from flask import Flask, jsonify, send_file, request
from flask_cors import CORS

# ── Solana imports ────────────────────────────────────────────────────────────
from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from solders.keypair import Keypair
from solders.transaction import Transaction
from solders.message import Message
from solders.hash import Hash
from spl.memo.instructions import create_memo, MemoParams

# ── QR ────────────────────────────────────────────────────────────────────────
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer

app = Flask(__name__)
CORS(app)

# ── Config ────────────────────────────────────────────────────────────────────
SOLANA_RPC   = "https://api.devnet.solana.com"
VERIFY_BASE  = os.getenv("VERIFY_BASE_URL", "http://localhost:5000/verify")
DB_FILE      = "diamonds.json"   # flat-file "database" — perfect for hackathon

# One throwaway keypair as the signing wallet.
# In production you'd load this from env / secret manager.
WALLET = Keypair()


# ── Flat-file DB helpers ──────────────────────────────────────────────────────
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE) as f:
            return json.load(f)
    return {}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)


# ── Solana memo tx ────────────────────────────────────────────────────────────
def anchor_to_solana(diamond_id: str, payload_hash: str) -> str:
    """
    Write a memo tx to devnet containing the diamond ID + payload hash.
    Returns the tx signature string, or a mock sig if devnet is unreachable.
    """
    try:
        client = Client(SOLANA_RPC)
        blockhash_resp = client.get_latest_blockhash()
        blockhash: Hash = blockhash_resp.value.blockhash

        memo_text = f"diamondchain:{diamond_id}:{payload_hash}"
        memo_ix = create_memo(MemoParams(
            program_id=MemoParams.__dataclass_fields__["program_id"].default
                if hasattr(MemoParams, "__dataclass_fields__") else
                __import__("solders.pubkey", fromlist=["Pubkey"]).Pubkey.from_string(
                    "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"
                ),
            signer=WALLET.pubkey(),
            message=memo_text.encode(),
        ))

        msg = Message.new_with_blockhash(
            [memo_ix], WALLET.pubkey(), blockhash
        )
        tx = Transaction([WALLET], msg, blockhash)
        resp = client.send_transaction(
            tx, opts=TxOpts(skip_preflight=False, preflight_commitment="confirmed")
        )
        return str(resp.value)

    except Exception as e:
        # Devnet unreachable (rate limit, network, etc.) — return a deterministic
        # mock signature so the rest of the demo still works locally.
        print(f"[solana] devnet unavailable ({e}), using mock sig")
        mock = hashlib.sha256(f"{diamond_id}:{payload_hash}:{time.time()}".encode()).hexdigest()
        return f"MOCK_{mock[:44]}"


# ── Diamond ID generator ──────────────────────────────────────────────────────
def make_diamond_id(country_code: str) -> str:
    year = datetime.utcnow().year
    suffix = hashlib.sha256(f"{country_code}{time.time()}".encode()).hexdigest()[:5].upper()
    existing = load_db()
    seq = str(len(existing) + 1).zfill(5)
    return f"DC-{year}-{country_code}-{seq}{suffix}"


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/register", methods=["POST"])
def register():
    """
    Register a diamond. Accepts JSON body:
    {
      "name":        "Round Brilliant · 1.24ct",
      "origin":      "Botswana, Jwaneng",
      "country_code":"BW",
      "grade":       "D / VVS1 / Excellent",
      "cert":        "GIA 6482910337",
      "miner":       "Debswana",
      "weight_ct":   1.24,
      "custody": [                          # optional starting custody chain
        {"event": "Extracted & registered", "location": "Jwaneng Mine, Botswana", "actor": "Debswana"}
      ]
    }
    """
    data = request.get_json(force=True)

    required = ["name", "origin", "country_code", "grade", "cert", "miner"]
    missing  = [k for k in required if k not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    diamond_id   = make_diamond_id(data["country_code"])
    registered   = datetime.utcnow().strftime("%d %b %Y")
    payload_hash = hashlib.sha256(
        json.dumps({**data, "id": diamond_id}, sort_keys=True).encode()
    ).hexdigest()

    tx_sig = anchor_to_solana(diamond_id, payload_hash)

    # Build the passport record
    custody = data.get("custody", [])
    if not custody:
        custody = [{
            "event":    "Extracted & registered",
            "location": data["origin"],
            "actor":    data["miner"],
            "date":     registered,
            "tx":       tx_sig,
            "status":   "done",
        }]
    else:
        for step in custody:
            step.setdefault("tx",     tx_sig)
            step.setdefault("date",   registered)
            step.setdefault("status", "done")

    passport = {
        "id":           diamond_id,
        "name":         data["name"],
        "origin":       data["origin"],
        "grade":        data["grade"],
        "cert":         data["cert"],
        "miner":        data["miner"],
        "weight_ct":    data.get("weight_ct"),
        "registered":   registered,
        "trust_score":  94,           # static for MVP; wire to real scoring later
        "tx_signature": tx_sig,
        "payload_hash": payload_hash,
        "custody":      custody,
    }

    db = load_db()
    db[diamond_id] = passport
    save_db(db)

    return jsonify({
        "diamond_id":   diamond_id,
        "tx_signature": tx_sig,
        "verify_url":   f"{VERIFY_BASE}/{diamond_id}",
        "passport":     passport,
    }), 201


@app.route("/verify/<diamond_id>", methods=["GET"])
def verify(diamond_id):
    db = load_db()
    if diamond_id not in db:
        return jsonify({"error": "Diamond not found"}), 404
    return jsonify(db[diamond_id])


@app.route("/qr/<diamond_id>", methods=["GET"])
def qr_code(diamond_id):
    db = load_db()
    if diamond_id not in db:
        return jsonify({"error": "Diamond not found"}), 404

    url = f"{VERIFY_BASE}/{diamond_id}"
    qr  = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        fill_color="#534AB7",
        back_color="white",
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/diamonds", methods=["GET"])
def list_diamonds():
    return jsonify(list(load_db().values()))

@app.route("/")
def index():
    return send_file("verify.html")

if __name__ == "__main__":
    print(f"Wallet pubkey: {WALLET.pubkey()}")
    print("Endpoints:")
    print("  POST /register")
    print("  GET  /verify/<id>")
    print("  GET  /qr/<id>")
    print("  GET  /diamonds")
    app.run(debug=True, port=5000)
