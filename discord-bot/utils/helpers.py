import random
from itertools import combinations

def best_team_partition(players, match_size):
    random.shuffle(players)
    k = match_size // 2
    all_indices = set(range(len(players)))
    min_diff = float('inf')
    best_team1, best_team2 = None, None

    for team1_indices in combinations(range(len(players)), k):
        team1 = [players[i] for i in team1_indices]
        team2 = [players[i] for i in all_indices - set(team1_indices)]
        score_diff = abs(sum(p["elo"] for p in team1) - sum(p["elo"] for p in team2))

        if score_diff < min_diff:
            min_diff = score_diff
            best_team1, best_team2 = team1, team2

    return best_team1, best_team2, [], 1
