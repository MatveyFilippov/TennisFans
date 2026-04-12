from datetime import datetime
import settings
from functools import lru_cache
import networkx as nx


@lru_cache(maxsize=10_000)
def __calculate_players_pair_weight(last_played: datetime | None, current_time: datetime) -> float:
    if last_played is None:
        return 0.0
    days_since_played = (current_time - last_played).total_seconds() / 86400
    return (100.0 * (0.9 ** min(days_since_played, 30))) if days_since_played > 0 else float("inf")


def find_optimal_players_pairs(all_player_ids: set[int], players_pair_last_play: dict[tuple[int, int], datetime]) -> list[tuple[int, int]]:
    if len(all_player_ids) % 2 != 0:
        raise ValueError("Quantity of players must be even")

    current_time = datetime.now(tz=settings.BACKEND_TIMEZONE)
    all_player_ids = list(sorted(all_player_ids))
    players_pair_last_play = {
        tuple(sorted(players_ids_pair)): last_played
        for players_ids_pair, last_played in players_pair_last_play.items()
    }

    weighted_graph = nx.Graph()
    weighted_graph.add_nodes_from(all_player_ids)

    for i, player1_id in enumerate(all_player_ids):
        for player2_id in all_player_ids[i + 1:]:
            last_played = players_pair_last_play.get((player1_id, player2_id))
            weight = __calculate_players_pair_weight(last_played, current_time)
            weighted_graph.add_edge(player1_id, player2_id, weight=weight)

    matching = nx.min_weight_matching(weighted_graph, weight="weight")
    return [tuple(pair) for pair in matching]
