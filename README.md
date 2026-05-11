# DiamondChain

The trust layer for diamonds. Colosseum hackathon submission.

## What it does
Gives every diamond a tamper-proof digital passport anchored on Solana,
tracking it from mine to market. Consumers verify a stone's full history
by scanning a QR code — no app, no account needed.

## Stack
Python, Flask, Solana devnet, HTML/JS

## Run it
pip install solana solders flask flask-cors qrcode[pil]
python backend.py

Open: http://localhost:5000/verify/<diamond-id>
