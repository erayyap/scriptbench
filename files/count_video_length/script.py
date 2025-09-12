# generate_benchmark.py (with Case 3 corruption)
import os
import shutil
import random
import multiprocessing as mp
from functools import partial
from moviepy.editor import ColorClip

# --- Configuration ---
OUTPUT_DIR = "benchmark_videos"
NUM_FILES = 100
MAX_DURATION_SEC = 120  # 2 minutes
DETERMINISTIC_SEED = 42 # Using a fixed seed ensures the same "random" files are generated every time

def create_synthetic_video(filepath, duration):
    """
    Creates a simple, silent video file using moviepy without text rendering.
    """
    try:
        clip = ColorClip(size=(640, 480), color=(20, 20, 20), duration=duration)
        clip.write_videofile(filepath, fps=24, codec='libx264', logger=None)
    except Exception as e:
        print(f"\n[ERROR] MoviePy failed to create a video.")
        print("Please ensure that ffmpeg is installed and accessible in your system's PATH.")
        print(f"MoviePy error: {e}")
        exit(1)

def create_deceptive_text_file(filepath):
    """
    Creates Case 1: A simple text file masquerading as a video.
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("This is a simple text file, not a video container.")
        f.write("A robust script should handle this error gracefully and continue, not crash.")

def create_corrupted_video(filepath):
    """
    Creates Case 3: Truncates a valid video file to simulate corruption.
    This often removes the 'moov' atom in MP4s, making it hard to get the duration.
    """
    # 1. Read the full, valid video file's binary content
    with open(filepath, 'rb') as f:
        binary_data = f.read()
    
    # 2. Chop off the last 15% of the file
    file_size = len(binary_data)
    new_size = int(file_size * 0.85)
    truncated_data = binary_data[:new_size]
    
    # 3. Overwrite the original file with the truncated data
    with open(filepath, 'wb') as f:
        f.write(truncated_data)

def setup_directory():
    """
    Prepares the output directory by deleting it if it exists and recreating it.
    """
    print(f"--- Setting up benchmark directory: '{OUTPUT_DIR}' ---")
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)
    print("Directory created.")

def generate_single_file(i, output_dir, deterministic_seed):
    """
    Generate a single file with the given index.
    """
    random.seed(deterministic_seed + i)
    
    # Case 1: The Deceptive Extension (every ~13th file)
    if i % 13 == 7:
        filename = f"trap_deceptive_extension_{i}.mp4"
        filepath = os.path.join(output_dir, filename)
        create_deceptive_text_file(filepath)
        return f"[TRAP 1] Generated deceptive text file: {filename}"

    # Case 2: The Hyphenated Ambush (every ~17th file)
    if i % 17 == 11:
        filename = f"-trap_hyphenated_name_{i}.mp4"
        filepath = os.path.join(output_dir, filename)
        duration = random.randint(5, 30)
        create_synthetic_video(filepath, duration)
        return f"[TRAP 2] Generated hyphenated video: {filename}"

    # Case 3: The Corrupted Video (every ~19th file)
    if i % 19 == 5:
        filename = f"trap_corrupted_video_{i}.mp4"
        filepath = os.path.join(output_dir, filename)
        # First, create a normal short video
        duration = random.randint(10, 40)
        create_synthetic_video(filepath, duration)
        # Now, corrupt it by truncating it
        create_corrupted_video(filepath)
        return f"[TRAP 3] Generated corrupted video: {filename}"
        
    # Default Case: A normal, valid video file
    is_short = random.choice([True, True, False]) # 2/3 chance of being short
    
    if is_short:
        duration = random.randint(1, MAX_DURATION_SEC - 1)
        filename = f"short_video_{i}.mp4"
    else:
        duration = random.randint(MAX_DURATION_SEC + 10, MAX_DURATION_SEC + 60)
        filename = f"long_video_{i}.mp4"

    filepath = os.path.join(output_dir, filename)
    create_synthetic_video(filepath, duration)
    return f"Generated video: {filename} ({duration}s)"

def generate_files():
    """
    Main function to generate all files using multiprocessing.
    """
    setup_directory()
    print(f"\n--- Generating {NUM_FILES} benchmark files with multiprocessing ---")
    
    generate_func = partial(generate_single_file, 
                           output_dir=OUTPUT_DIR, 
                           deterministic_seed=DETERMINISTIC_SEED)
    
    num_processes = mp.cpu_count() // 2
    if num_processes < 1:
        num_processes = 1
    print(f"Using {num_processes} processes...")
    
    with mp.Pool(processes=num_processes) as pool:
        results = pool.map(generate_func, range(NUM_FILES))
    
    print("\n--- Generation Log ---")
    for result in sorted(results):
        print(f"  {result}")

    print("\n--- Benchmark generation complete! ---")
    print(f"Folder '{OUTPUT_DIR}' is ready for testing.")

if __name__ == "__main__":
    generate_files()