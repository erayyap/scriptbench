import csv
import random
import chess
from tqdm import tqdm

def create_solvable_invalidations(moves: list[str], num_to_create: int) -> tuple[list[str], list[str]]:
    """
    Takes a list of valid moves and finds positions where there was only ONE
    legal move possible (a "forced move"). It replaces these moves with '[INVALID]'
    to create a uniquely solvable puzzle. It will attempt to find the specified
    number of such positions.
    """
    # A game must be reasonably long to find multiple invalidation points.
    if len(moves) < 20 or num_to_create < 1:
        return None, None

    candidate_indices = list(range(4, len(moves) - 2))
    random.shuffle(candidate_indices)

    target_info = {}

    for index in candidate_indices:
        if len(target_info) >= num_to_create:
            break

        board = chess.Board()
        try:
            for move_san in moves[:index]:
                board.push_san(move_san)
        except (ValueError, chess.IllegalMoveError):
            # This is a failsafe in case the initial game sequence has an issue.
            continue

        # --- THE FIX ---
        # `board.legal_moves` is a generator. We must convert it to a list
        # before we can check its length with len().
        legal_moves_list = list(board.legal_moves)

        if len(legal_moves_list) == 1:
            # Success! This is a uniquely solvable, forced-move position.
            original_move = moves[index]
            target_info[index] = original_move

    # If we couldn't find enough forced moves, we can't create the puzzle.
    if len(target_info) < num_to_create:
        return None, None
    
    modified_moves = list(moves)
    # Sort the indices to ensure the targets are in the correct game order
    # and we modify the list correctly.
    sorted_indices = sorted(target_info.keys())
    final_targets = [target_info[i] for i in sorted_indices]
    
    for i in sorted_indices:
        modified_moves[i] = "[INVALID]"
        
    return modified_moves, final_targets


def generate_random_game(max_moves=400):
    """Generate a random chess game using a robust method."""
    board = chess.Board()
    moves = []
    
    for _ in range(max_moves):
        if board.is_game_over():
            break
        
        # Also need to convert to a list here to pick a random choice.
        legal_moves_list = list(board.legal_moves)
        if not legal_moves_list:
            break
            
        selected_move = random.choice(legal_moves_list)
        
        try:
            move_san = board.san(selected_move)
            board.push(selected_move)
            moves.append(move_san)
        except (ValueError, chess.IllegalMoveError):
            # This can happen in rare edge cases (e.g., with promotions).
            break
    
    result = board.result(claim_draw=True)
    return moves, result

def validate_game_sequence(moves: list[str]) -> bool:
    """Validate that an entire game sequence contains only legal moves."""
    board = chess.Board()
    for move_san in moves:
        try:
            board.push_san(move_san)
        except (ValueError, chess.IllegalMoveError, chess.AmbiguousMoveError):
            return False
    return True

def generate_player_name():
    """Generate random player names."""
    first_names = ["Magnus", "Hikaru", "Fabiano", "Ian", "Levon", "Wesley", "Ding", "Wei"]
    last_names = ["Carlsen", "Nakamura", "Caruana", "Giri", "So", "Tal", "Fischer", "Liren"]
    return f"{random.choice(first_names)} {random.choice(last_names)}"

def generate_chess_csv(filename="incomplete_games_final.csv", num_games=200):
    """
    Generate a CSV file with chess games containing guaranteed solvable [INVALID] moves.
    Solvability is defined as a "forced move" (only one legal move available).
    Each game will have multiple [INVALID] moves.
    """
    fieldnames = ['game_id', 'white_player', 'black_player', 'moves', 'result', 'target']
    
    games_data = []
    # Finding games with multiple forced moves is harder, so we increase the attempts.
    max_attempts = num_games * 100 
    
    pbar = tqdm(total=num_games, desc="Generating Multi-Invalid Games")

    for _ in range(max_attempts):
        if len(games_data) >= num_games:
            break

        moves, result = generate_random_game(random.randint(100, 400))
        
        if not validate_game_sequence(moves):
            continue
        
        # We need longer games to have a better chance of finding multiple forced moves.
        if len(moves) < 50:
            continue

        # --- KEY CHANGE: Generate more than one invalid move ---
        # Each puzzle will now have between 2 and 4 invalid moves to solve.
        num_invalid_to_create = random.randint(2, 4)
        modified_moves, original_moves = create_solvable_invalidations(moves, num_invalid_to_create)
        
        if modified_moves and original_moves:
            game_id = len(games_data) + 1
            row = {
                'game_id': f"GAME_{game_id:04d}",
                'white_player': generate_player_name(),
                'black_player': generate_player_name(),
                'moves': ' '.join(modified_moves),
                'result': result,
                'target': ' '.join(original_moves) # Joins multiple moves into a single target string
            }
            games_data.append(row)
            pbar.update(1)

    pbar.close()

    if len(games_data) < num_games:
        print(f"\nWarning: Only generated {len(games_data)} of {num_games} requested games. Finding games with multiple forced moves is difficult.")

    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(games_data)
        
    print(f"\nSuccessfully generated {len(games_data)} solvable games in {filename}")

if __name__ == "__main__":
    generate_chess_csv()