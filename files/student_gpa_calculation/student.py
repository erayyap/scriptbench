# SCRIPT USED TO GENERATE THE STUDENTS GRADES. LLM WONT SEE THIS.

import csv
import random
import numpy as np
import os

# --- Configuration Constants ---
FILENAME = 'student_grades.csv'
NUM_STUDENTS = 200
STUDENTS_PER_SECTION = 100
TARGET_QUIZ_AVG = 85.0

def generate_student_data(filename):
    """
    Generates a CSV file with noisy student grade data for two sections.
    """
    print(f"Generating noisy student data in '{filename}'...")
    
    header = [
        'student_id', 'section', 
        'hw1', 'hw2', 'hw3', 'hw4', 
        'quiz1', 'quiz2', 'quiz3', 'quiz4', 'quiz5',
        'midterm', 'final'
    ]

    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)

        for i in range(NUM_STUDENTS):
            student_id = 10001 + i
            section = 1 if i < STUDENTS_PER_SECTION else 2
            
            # Helper function to generate a score or leave it blank
            def generate_score(mean, std_dev, miss_chance=0.05):
                if random.random() < miss_chance:
                    return ''  # Represents a missed assignment (0)
                score = np.random.normal(mean, std_dev)
                return round(max(0, min(100, score)), 2)

            # Section 1 students tend to score slightly higher on quizzes
            quiz_mean = 85 if section == 1 else 81
            
            row = [
                student_id, section,
                generate_score(88, 10), generate_score(90, 8), generate_score(85, 12), generate_score(92, 7),
                generate_score(quiz_mean, 15), generate_score(quiz_mean, 15), generate_score(quiz_mean, 15),
                generate_score(quiz_mean, 15), generate_score(quiz_mean, 15),
                generate_score(78, 13), generate_score(76, 14)
            ]
            writer.writerow(row)
    print("Data generation complete.")

def get_gpa_from_percentage(percentage):
    """Converts a final course percentage to a GPA based on the syllabus scale."""
    if percentage >= 93.0: return 4.0
    if percentage >= 90.0: return 3.7
    if percentage >= 87.0: return 3.3
    if percentage >= 83.0: return 3.0
    if percentage >= 80.0: return 2.7
    if percentage >= 77.0: return 2.3
    if percentage >= 73.0: return 2.0
    if percentage >= 70.0: return 1.7
    if percentage >= 60.0: return 1.0
    return 0.0

def calculate_grades(filename):
    """
    Reads student data, calculates final grades, and computes the average GPA for Section 1.
    """
    if not os.path.exists(filename):
        print(f"Error: File '{filename}' not found. Please generate it first.")
        return

    print("\n--- Starting Grade Calculation Process ---")

    # Step 1: Read all data
    students_data = []
    with open(filename, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            students_data.append(row)

    def parse_score(score_str):
        return float(score_str) if score_str else 0.0

    # Step 2: Pre-calculate Raw Quiz Averages for each section
    section1_raw_quiz_averages, section2_raw_quiz_averages = [], []
    for student in students_data:
        quiz_scores = [parse_score(student[f'quiz{i}']) for i in range(1, 6)]
        quiz_scores.sort()
        avg_top_4_quizzes = sum(quiz_scores[1:]) / 4.0
        
        if int(student['section']) == 1:
            section1_raw_quiz_averages.append(avg_top_4_quizzes)
        else:
            section2_raw_quiz_averages.append(avg_top_4_quizzes)
    
    sec1_avg, sec2_avg = np.mean(section1_raw_quiz_averages), np.mean(section2_raw_quiz_averages)
    
    print("\n--- Pre-Calculation Summary ---")
    print(f"Target Quiz Average for Normalization: {TARGET_QUIZ_AVG:.2f}")
    print(f"Calculated Raw Quiz Average for Section 1: {sec1_avg:.2f}")
    print(f"Calculated Raw Quiz Average for Section 2: {sec2_avg:.2f}\n")

    # Step 3: Process each student and collect GPA data for Section 1
    section1_gpas = []

    for student in students_data:
        student_id, section = student['student_id'], int(student['section'])
        print(f"--- Calculating Grade for Student ID: {student_id} (Section: {section}) ---")

        # 1. Homework Calculation
        hw_scores = sorted([parse_score(student[f'hw{i}']) for i in range(1, 5)])
        avg_top_3_hw = sum(hw_scores[1:]) / 3.0
        print(f"  [HW]   Final Homework Component Score: {avg_top_3_hw:.2f}")
        
        # 2. Quiz Calculation
        quiz_scores = sorted([parse_score(student[f'quiz{i}']) for i in range(1, 6)])
        raw_quiz_avg = sum(quiz_scores[1:]) / 4.0
        section_avg_for_norm = sec1_avg if section == 1 else sec2_avg
        normalized_quiz_score = min(100.0, raw_quiz_avg * (TARGET_QUIZ_AVG / section_avg_for_norm))
        print(f"  [Quiz] Final Quiz Component Score (Normalized): {normalized_quiz_score:.2f}")

        # 3. Midterm Replacement
        midterm_score = parse_score(student['midterm'])
        final_score = parse_score(student['final'])
        effective_midterm_score = max(midterm_score, final_score)
        if effective_midterm_score == final_score and midterm_score != final_score:
            print(f"  [Exam] Midterm score ({midterm_score:.2f}) replaced by higher final score ({final_score:.2f}).")
        print(f"  [Exam] Effective Midterm Component Score: {effective_midterm_score:.2f}")

        # 4. Final Grade Assembly
        hw_contrib = avg_top_3_hw * 0.30
        quiz_contrib = normalized_quiz_score * 0.10
        midterm_contrib = effective_midterm_score * 0.25
        final_contrib = final_score * 0.35
        
        final_grade = hw_contrib + quiz_contrib + midterm_contrib + final_contrib
        
        # 5. GPA Conversion
        student_gpa = get_gpa_from_percentage(final_grade)
        
        print(f"  [Total] FINAL COURSE PERCENTAGE: {final_grade:.2f}")
        print(f"  [Total] Corresponding GPA: {student_gpa:.1f}\n")
        
        # Store the GPA if the student is in Section 1
        if section == 1:
            section1_gpas.append(student_gpa)

    # --- Step 4: Final Summary ---
    avg_gpa_sec1 = np.mean(section1_gpas)
    print("---" * 15)
    print("\n--- Final Course Summary ---")
    print(f"Average GPA for Section 1: {avg_gpa_sec1:.2f}")
    print("\n---" * 15)


if __name__ == "__main__":
    generate_student_data(FILENAME)
    calculate_grades(FILENAME)