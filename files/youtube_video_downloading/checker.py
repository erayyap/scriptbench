#!/usr/bin/env python3
import os
import glob
import subprocess
import json
import sys

def check_video_criteria(video_path):
    """
    Check if video meets all criteria:
    - Resolution: 1280x720
    - Has audio track
    - Duration: 292 seconds ±1 second (291-293 seconds)
    """
    try:
        # Use ffprobe to get video information
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        # Initialize criteria checks
        has_correct_resolution = False
        has_audio = False
        correct_duration = False
        
        # Check streams for video resolution and audio
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                width = stream.get('width')
                height = stream.get('height')
                if width == 1280 and height == 720:
                    has_correct_resolution = True
            elif stream.get('codec_type') == 'audio':
                has_audio = True
        
        # Check duration
        duration = float(data.get('format', {}).get('duration', 0))
        if 291 <= duration <= 293:
            correct_duration = True
        
        # Return True only if all criteria are met
        return has_correct_resolution and has_audio and correct_duration
        
    except (subprocess.CalledProcessError, json.JSONDecodeError, ValueError, KeyError):
        return False

def main():
    # Common video file extensions
    video_extensions = ['mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm', 'm4v', '3gp', 'ogv', 'ts', 'mts', 'vob']
    
    # Search for video files matching "video.*"
    video_files = []
    for ext in video_extensions:
        pattern = f"video.{ext}"
        matches = glob.glob(pattern, recursive=False)
        video_files.extend(matches)
    
    # If no video files found, return FALSE
    if not video_files:
        print("FALSE")
        return
    
    # Check each video file found
    for video_file in video_files:
        if check_video_criteria(video_file):
            print("TRUE")
            return
    
    # If no video meets criteria, return FALSE
    print("FALSE")

if __name__ == "__main__":
    main()