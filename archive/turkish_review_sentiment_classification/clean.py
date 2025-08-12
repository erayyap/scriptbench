import csv
import os
import random
import copy

def sample_and_process_csv(input_file, unfilled_output="unfilled_sample.csv", filled_output="filled_sample.csv", sample_size=100):
    """
    Randomly samples rows where 'Görüş' field is longer than 50 characters and creates two CSV files:
    - unfilled: with empty 'Durum' field
    - filled: with original 'Durum' field intact
    
    Args:
        input_file (str): Path to the input CSV file
        unfilled_output (str): Path to the unfilled output CSV file
        filled_output (str): Path to the filled output CSV file
        sample_size (int): Number of rows to sample (default: 100)
    """
    
    try:
        with open(input_file, 'r', encoding='utf-16', newline='') as file:
            # Use csv.Sniffer to detect the delimiter
            sample = file.read(1024)
            file.seek(0)
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
            
            reader = csv.reader(file, delimiter=delimiter)
            
            # Process header row
            header = next(reader)
            
            # Find the indices of the required columns
            try:
                durum_column_index = header.index('Durum')
                gorus_column_index = header.index('Görüş')
                print(f"Found 'Durum' column at index {durum_column_index}")
                print(f"Found 'Görüş' column at index {gorus_column_index}")
            except ValueError as e:
                print(f"Error: Required column not found - {str(e)}")
                return False
            
            # Collect eligible rows (where Görüş field is longer than 50 characters)
            eligible_rows = []
            
            for row in reader:
                # Ensure the row has enough columns
                while len(row) <= max(durum_column_index, gorus_column_index):
                    row.append('')
                
                # Check if Görüş field is longer than 50 characters
                if len(row[gorus_column_index].strip()) > 50:
                    eligible_rows.append(row)
            
            print(f"Found {len(eligible_rows)} rows with 'Görüş' field longer than 50 characters")
            
            # Sample rows randomly
            if len(eligible_rows) < sample_size:
                print(f"Warning: Only {len(eligible_rows)} eligible rows found, using all of them")
                sampled_rows = eligible_rows
            else:
                sampled_rows = random.sample(eligible_rows, sample_size)
                print(f"Randomly sampled {sample_size} rows")
            
            # Create unfilled version (empty Durum field)
            unfilled_rows = [header]
            for row in sampled_rows:
                unfilled_row = copy.deepcopy(row)
                unfilled_row[durum_column_index] = ''
                unfilled_rows.append(unfilled_row)
            
            # Create filled version (original Durum field intact)
            filled_rows = [header] + sampled_rows
            
            # Write unfilled CSV
            with open(unfilled_output, 'w', encoding='utf-16', newline='') as file:
                writer = csv.writer(file, delimiter=delimiter)
                writer.writerows(unfilled_rows)
            
            # Write filled CSV
            with open(filled_output, 'w', encoding='utf-16', newline='') as file:
                writer = csv.writer(file, delimiter=delimiter)
                writer.writerows(filled_rows)
            
            print(f"Successfully created two sample files:")
            print(f"  - Unfilled (empty Durum): '{unfilled_output}' with {len(sampled_rows)} data rows")
            print(f"  - Filled (original Durum): '{filled_output}' with {len(sampled_rows)} data rows")
            
            return True
            
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found")
        return False
    except UnicodeDecodeError:
        print(f"Error: Unable to decode file '{input_file}' as UTF-16")
        print("Please check if the file is actually encoded in UTF-16")
        return False
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return False

def clean_durum_field(input_file, output_file=None):
    """
    Opens a CSV file in UTF-16 encoding and empties the 'Durum' field.
    
    Args:
        input_file (str): Path to the input CSV file
        output_file (str, optional): Path to the output CSV file. 
                                   If None, overwrites the input file.
    """
    
    # If no output file specified, overwrite the input file
    if output_file is None:
        output_file = input_file
    
    # Read the CSV file
    rows = []
    durum_column_index = None
    
    try:
        with open(input_file, 'r', encoding='utf-16', newline='') as file:
            # Use csv.Sniffer to detect the delimiter
            sample = file.read(1024)
            file.seek(0)
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
            
            reader = csv.reader(file, delimiter=delimiter)
            
            # Process header row
            header = next(reader)
            
            # Find the index of the 'Durum' column
            try:
                durum_column_index = header.index('Durum')
                print(f"Found 'Durum' column at index {durum_column_index}")
            except ValueError:
                print("Error: 'Durum' column not found in the CSV file")
                return False
            
            rows.append(header)
            
            # Process data rows
            for row in reader:
                # Ensure the row has enough columns
                while len(row) <= durum_column_index:
                    row.append('')
                
                # Empty the 'Durum' field
                row[durum_column_index] = ''
                rows.append(row)
        
        # Write the modified data back to file
        with open(output_file, 'w', encoding='utf-16', newline='') as file:
            writer = csv.writer(file, delimiter=delimiter)
            writer.writerows(rows)
        
        print(f"Successfully processed {len(rows)-1} data rows")
        print(f"'Durum' field has been emptied in all rows")
        
        if input_file == output_file:
            print(f"File '{input_file}' has been updated")
        else:
            print(f"Modified data saved to '{output_file}'")
        
        return True
        
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found")
        return False
    except UnicodeDecodeError:
        print(f"Error: Unable to decode file '{input_file}' as UTF-16")
        print("Please check if the file is actually encoded in UTF-16")
        return False
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return False

# Example usage
if __name__ == "__main__":
    # Replace 'your_file.csv' with the actual path to your CSV file
    input_csv_file = "./magaza_yorumlari_duygu_analizi.csv"
    
    # NEW: Sample 100 rows with Görüş field longer than 50 characters
    print("=== Creating sampled datasets ===")
    sample_and_process_csv(input_csv_file, "unfilled.csv", "filled.csv", 100)
    
    print("\n=== Original function (clean all Durum fields) ===")
    # Option 1: Overwrite the original file
    #clean_durum_field(input_csv_file)
    
    # Option 2: Save to a new file (uncomment the line below)
    # clean_durum_field(input_csv_file, "modified_file.csv")