# Merlin Oracle Almanac — agent instructions

Read `RESEARCH-ENGINE.md` before changing the research engine, Kalshi vault, Binance ingest, reconstruction snapshots, backtests, or Merlin feature wiring.

This repo is a **research/forensics notebook for publicly observable Kalshi trading behavior**. It is not a trading bot and it is not a system for private account data.

## Standing rules

- Public market activity is data. Private credentials, private API keys, private account history, and anything not legitimately public are out of scope. Never pursue or infer them through unauthorized means.
- Reconstruct what was knowable at entry time T. Do not start from why a trade won.
- Kalshi is settlement truth. Binance (or another high-resolution feed) is sight. Do not treat those prices as identical. If they diverge past a threshold, the model goes quiet.
- Store raw observations separately from derived features. Merlin stays an experimental layer (Model C), never silent evidence.
- Every prediction feature must have been available at the simulated decision timestamp. Settlement does not belong in the T vector.
- Do not optimize for profit first. Understand, then test against a control group, then paper trade.

## Path map

`research-path.html` is the architecture pictograph. The Almanac UI surfaces the same charter on the Research engine screen.
