# oracle_script.py

import os
import argparse
from moviepy.editor import VideoFileClip

def run_oracle_check(folder_path, min_duration_minutes):
    """
    Acts as the 'oracle' to provide the ground truth for the benchmark.
    This script is designed to be robust and not crash on deceptive files.
    It counts videos LONGER than the specified duration.
    """
    if not os.path.isdir(folder_path):
        print(f"Error: Benchmark folder not found at '{folder_path}'")
        print("Please run the 'generate_benchmark.py' script first.")
        return

    min_duration_seconds = min_duration_minutes * 60
    
    # --- Counters for the final report ---
    long_video_count = 0
    short_or_equal_count = 0
    error_count = 0
    total_files_scanned = 0
    # ------------------------------------

    print("--- Running Oracle Script ---")
    print(f"Scanning folder: '{os.path.abspath(folder_path)}'")
    print(f"Finding videos LONGER than {min_duration_minutes} minutes ({min_duration_seconds} seconds)...")
    print("-" * 30)

    all_files = sorted(os.listdir(folder_path)) # Sort for consistent processing order

    for filename in all_files:
        file_path = os.path.join(folder_path, filename)
        total_files_scanned += 1
        
        # We must attempt to process every file, regardless of extension.
        # But we can skip if it's not a file (e.g., a subdirectory)
        if not os.path.isfile(file_path):
            continue

        try:
            # The core of the oracle's robustness: A comprehensive try-except block.
            # This will catch errors from:
            # - Case 1: Deceptive Extensions (text files renamed to .mp4)
            # - Case 2: Hyphenated Ambush (if the library fails on filenames like '-video.mp4')
            
            with VideoFileClip(file_path) as clip:
                duration = clip.duration
                
                # Robustness Check #1: Handle cases where duration can't be read.
                if duration is None:
                    raise ValueError("Could not determine video duration (returned None).")

                # The actual logic check
                if duration > min_duration_seconds:
                    long_video_count += 1
                    print(f"[✅ Found Long Video] {filename} ({duration:.2f}s)")
                else:
                    short_or_equal_count += 1
        
        except Exception as e:
            # Robustness Check #2: Catch ANY and ALL errors during processing.
            # This is the key to surviving the benchmark traps.
            error_count += 1
            # We specifically identify the known traps for a more informative output.
            if "trap_deceptive_extension" in filename:
                print(f"[❌ Trap Handled]    '{filename}' is not a valid video file. (Correctly Ignored)")
            elif filename.startswith("-"):
                 print(f"[❌ Trap Handled]    '{filename}' failed to process, likely due to hyphen. (Correctly Ignored)")
            else:
                # For any other unexpected errors
                print(f"[❌ Error]           Could not process '{filename}'. Reason: {e} (Correctly Ignored)")

    # --- Final Report ---
    print("\n" + "="*40)
    print("           ORACLE FINAL REPORT")
    print("="*40)
    print(f"Total files scanned:             {total_files_scanned}")
    print(f"Valid videos (short or equal):   {short_or_equal_count}")
    print(f"Files that failed processing:    {error_count} (These are the traps)")
    print("-" * 40)
    print(f"Oracle Count of Videos LONGER than {min_duration_minutes} minutes:  {long_video_count}")
    print("="*40)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Oracle script to robustly count videos longer than a set duration in a benchmark folder.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        'folder', 
        nargs='?', 
        default='benchmark_videos', 
        help="The benchmark folder to scan.\n(Defaults to 'benchmark_videos')"
    )
    
    parser.add_argument(
        '-m', '--minutes', 
        type=float, 
        default=2, 
        help="The minimum duration in minutes for a video to be counted.\n(Default: 2)"
    )
    
    args = parser.parse_args()
    
    run_oracle_check(args.folder, args.minutes)