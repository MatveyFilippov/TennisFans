from . import dto
from datetime import datetime
import settings
from functools import lru_cache
import networkx as nx


@lru_cache(maxsize=10_000)
def __calculate_players_pair_weight(last_played: datetime | None, current_time: datetime) -> float:
    if last_played is None:
        return 1e9
    return (current_time - last_played).days


def find_optimal_players_pairs(all_players_id_dto: dict[int, dto.PlayerDTO], players_pair_dto_last_play: dict[dto.PlayersPairDTO, datetime]) -> list[dto.PlayersPairDTO]:
    current_time = datetime.now(tz=settings.PROJECT_TIMEZONE)
    all_player_ids = list(sorted(all_players_id_dto.keys()))

    player_ids_pair_last_play = {
        tuple(sorted([players_pair_dto.player1_dto.id, players_pair_dto.player2_dto.id])): last_played
        for players_pair_dto, last_played in players_pair_dto_last_play.items()
    }

    weighted_graph = nx.Graph()
    weighted_graph.add_nodes_from(all_player_ids)

    for i, player1_id in enumerate(all_player_ids):
        for player2_id in all_player_ids[i + 1:]:
            last_played = player_ids_pair_last_play.get((player1_id, player2_id))
            weight = __calculate_players_pair_weight(last_played, current_time)
            weighted_graph.add_edge(player1_id, player2_id, weight=weight)

    matching = nx.max_weight_matching(weighted_graph, weight="weight", maxcardinality=True)
    result = []
    for player_ids_pair in matching:
        player1_id, player2_id = sorted(player_ids_pair)
        result.append(dto.PlayersPairDTO(
            player1_dto=all_players_id_dto[player1_id],
            player2_dto=all_players_id_dto[player2_id],
        ))
    return result
