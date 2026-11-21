# Tournament formats and placements

Capacity denotes individual accepted players. Pending applications can exceed it. A roster must exactly fill capacity before the automatic reconciliation can build a schedule. A tournament in **Action required** needs an administrator to change the start time or delete it. Rosters and rules freeze on valid startup. The default scheduler checks every 30 seconds and runs during startup. There is no manual completion.

## Local standings

In singles each entry is one player. Fixed doubles treats each disjoint pair as an entry. Round robin uses the circle method, with one meeting per matchup per cycle. The optional interval schedules rounds from the configured start. The time zone affects display; actual result times are stored in UTC.

Order entries by wins, then head-to-head when exactly two share wins and their resolved encounters distinguish them. If still tied, compare set differential, game differential, sets won, and games won. Equal standings share their occupied rank range. Walkovers and forfeits add a win or loss without synthetic sets or games.

## Knockout and groups

Seed entries by accepted roster order or reproducibly shuffle with the recorded integer seed. In fixed doubles, the earliest accepted member defines the team's original order. Seeded power-of-two brackets advance players with byes directly into their first contested fixture. A match is instantiated once both opponents are known. The round of elimination determines a rank band such as 3–4, clipped to the number of entrants. No classification match is generated.

Group tournaments use serpentine seed allocation. Each group requires at least two entries and at least one nonqualifier. Once every group result is eligible, order qualifiers by group placement and group number. A draw using the tournament seed plus group position resolves any shared ranks needed for selection or seeding. Inspect the recorded draw in the audit log. Group nonqualifiers share the range after all playoff entries. A group dispute blocks dependent playoff results until resolved. If a verified correction changes the seeding, the earlier playoff outcomes are removed only after administrator confirmation when affected results had been recorded.

## Rotating doubles

Each group of four creates two short-lived match sides. With four players the three unique teammate pairings are used. At larger capacities the scheduler evaluates 96 seeded base rounds, scores candidate partner and opponent frequencies by circular distance, and rotates the best base round across all ordinal positions. Every player has the same number of fixtures and byes. The greedy bounded search minimizes repetition jointly across the generated schedule and does not guarantee exact partner/opponent frequencies at every capacity. Rotating standings rank individual players. Two-way head-to-head is skipped when the two players have also been teammates in a resolved match.

The capacity is capped at 128 to bound the number of synchronous fixture writes and the public schedule size. A maximum-capacity rotation or league generates thousands of fixtures. Set database and process resources accordingly. The initial rating implementation fully replays history on each material change.
