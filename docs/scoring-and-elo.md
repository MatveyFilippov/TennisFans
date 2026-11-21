# Scoring and Elo

- Standard best of three. Win two sets. A regular set ends 6–0 through 6–4, 7–5 or 7–6. Optional tie-break points at 7–6 require seven points and a margin of at least two, with the tie-break winner matching the set winner.
- Optional 10-point deciding match tie-break. Enter points in the third set fields after splitting the first two sets. It counts as a won set and adds zero games to the match total.
- Single set. The same regular set rules apply.
- Short match. A single set ends when the target is reached. With the default target of three and a deciding game, 3–0, 3–1 and 3–2 are valid. The tie-break alternative at target-minus-one allows points to be recorded. In win-by-two mode, the score must reach the target and lead by two if the opponent has reached target-minus-one.

Only tournaments have administrative outcomes. Walkover and forfeit record a winner and zero sets or games. Retirement can retain complete sets plus a final in-progress set. The standings count all resolved outcomes. Only a competitive finish contributes rating points.

## One rating

Every player starts at 1500, and the default K is 32. For side A, expected score is `1 / (1 + 10^((R_B - R_A) / 400))`. The winner gains `K × (1 - expected)` and the loser loses the same amount. A singles match between two players at 1500 therefore produces 1516 and 1484. For doubles, take the arithmetic mean of each side's current ratings. Each player on a side gets its full team delta. For example, a 1508-rated team losing to a 1492-rated team loses about 16.7363 points per player.

Replay orders competitive events by actual UTC timestamp and immutable UUID. It retains high decimal precision through the replay, persists 12 fractional digits for each point and displays whole-number Elo by default. Older submissions, disputes, reversals, and deletion can change every subsequent event across all tournaments. Updating K on an instance triggers a full replay under the startup lock. Coordinate the configuration across all workers before restarting any of them.
