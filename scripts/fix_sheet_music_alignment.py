#!/usr/bin/env python3
"""
Sheet Music Image Alignment Correction Script
Matches sheet music entries with their correct images using title-based matching
instead of position-based assignment.

Problem: 800+ sheet music images were assigned by scraping position (1st image = 1st entry)
but Google Sheet order doesn't match scraped order, causing misalignment.

Solution: Use sheet titles from sheet_data.csv to correctly match images to entries.
"""

import csv
import os
from pathlib import Path
from typing import Dict, List, Tuple
from difflib import SequenceMatcher

def load_sheet_data(csv_path: str) -> Dict[str, Dict]:
    """
    Load sheet_data.csv and create a dictionary keyed by title.
    
    Returns:
        Dict with title as key, containing all metadata including drive_file_id
    """
    sheet_data = {}
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = row.get('Name of Piece', '').strip()
            if title:
                sheet_data[title] = row
    
    print(f"✓ Loaded {len(sheet_data)} sheet music entries from sheet_data.csv")
    return sheet_data

def load_import_master(csv_path: str) -> List[Dict]:
    """
    Load import_master.csv to see current image assignments.
    
    Returns:
        List of dictionaries with current metadata
    """
    entries = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append(row)
    
    print(f"✓ Loaded {len(entries)} entries from import_master.csv")
    return entries

def find_images_by_category(images_dir: str, category: str) -> Dict[int, str]:
    """
    Find all images for a specific category (e.g., 'sheets', 'records').
    
    Args:
        images_dir: Path to images directory
        category: Category name (sheets, records, music, etc.)
    
    Returns:
        Dict mapping sequence number to full image path
    """
    images = {}
    category_path = Path(images_dir) / category
    
    if not category_path.exists():
        print(f"⚠ Category directory not found: {category_path}")
        return images
    
    for img_file in sorted(category_path.glob('*')):
        if img_file.is_file() and img_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
            # Extract sequence number from filename if present
            # Assumes naming like: SHE-0001.jpg or sheets_0001.jpg
            try:
                # Try to extract number from various naming conventions
                stem = img_file.stem
                if '-' in stem:
                    num_part = stem.split('-')[-1]
                elif '_' in stem:
                    num_part = stem.split('_')[-1]
                else:
                    num_part = stem
                
                if num_part.isdigit():
                    seq_num = int(num_part)
                    images[seq_num] = str(img_file)
            except (ValueError, IndexError):
                pass
    
    print(f"✓ Found {len(images)} images in {category} category")
    return images

def similarity_score(str1: str, str2: str) -> float:
    """
    Calculate similarity between two strings (0.0 to 1.0).
    Useful for fuzzy title matching.
    """
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

def create_correction_mapping(sheet_data: Dict[str, Dict], 
                             import_master: List[Dict],
                             images: Dict[int, str]) -> Dict[int, Dict]:
    """
    Create a mapping of corrected pairings.
    
    For each sheet music entry in import_master, find its correct image
    by matching the title from sheet_data.
    
    Args:
        sheet_data: Dictionary from sheet_data.csv keyed by title
        import_master: List from import_master.csv
        images: Dictionary of available images mapped by sequence number
    
    Returns:
        Dictionary with corrected mapping: entry_id -> {corrected_image, metadata}
    """
    correction_map = {}
    unmatched_entries = []
    
    for seq_num, img_path in images.items():
        # Find the entry at this position in import_master
        if seq_num <= len(import_master):
            entry = import_master[seq_num - 1]  # seq_num is 1-indexed
            
            # Get the title from import_master (if available)
            title_from_master = entry.get('Dublin Core:Title', '').strip()
            
            if title_from_master in sheet_data:
                # Direct match found
                sheet_info = sheet_data[title_from_master]
                correction_map[seq_num] = {
                    'sequence': seq_num,
                    'current_image': img_path,
                    'title': title_from_master,
                    'drive_file_id': sheet_info.get('drive_file_id', ''),
                    'media_type': sheet_info.get('Media Type (Sheet, Book, or Records)', ''),
                    'genre': sheet_info.get('Genre', ''),
                    'composer': sheet_info.get('Music By', ''),
                    'match_type': 'direct'
                }
            else:
                # No direct match - this is a problem entry
                unmatched_entries.append({
                    'sequence': seq_num,
                    'image': img_path,
                    'title_in_master': title_from_master
                })
    
    return correction_map, unmatched_entries

def generate_correction_report(correction_map: Dict, 
                              unmatched: List,
                              output_path: str = 'sheet_music_corrections.csv'):
    """
    Generate a report of all corrections made.
    
    Output includes:
    - Sequence number
    - Image path
    - Correct title
    - Drive file ID
    - Genre/type info
    """
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'sequence_number',
            'image_path',
            'correct_title',
            'media_type',
            'genre',
            'composer',
            'drive_file_id',
            'match_type',
            'status'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        # Write matched corrections
        for seq_num in sorted(correction_map.keys()):
            data = correction_map[seq_num]
            writer.writerow({
                'sequence_number': data['sequence'],
                'image_path': data['current_image'],
                'correct_title': data['title'],
                'media_type': data['media_type'],
                'genre': data['genre'],
                'composer': data['composer'],
                'drive_file_id': data['drive_file_id'],
                'match_type': data['match_type'],
                'status': 'CORRECTED'
            })
        
        # Write unmatched entries (need manual review)
        for entry in unmatched:
            writer.writerow({
                'sequence_number': entry['sequence'],
                'image_path': entry['image'],
                'correct_title': entry['title_in_master'],
                'status': 'UNMATCHED - REVIEW REQUIRED'
            })
    
    print(f"\n✓ Correction report generated: {output_path}")

def main():
    """Main execution function."""
    
    # Configuration
    sheet_data_path = 'sheet_data.csv'
    import_master_path = 'import_master.csv'
    images_dir = 'images'
    
    # Check if files exist
    if not os.path.exists(sheet_data_path):
        print(f"✗ Error: {sheet_data_path} not found")
        return
    
    if not os.path.exists(import_master_path):
        print(f"✗ Error: {import_master_path} not found")
        return
    
    print("=" * 60)
    print("SHEET MUSIC IMAGE ALIGNMENT CORRECTION TOOL")
    print("=" * 60)
    
    # Load data
    print("\n1. LOADING DATA...")
    sheet_data = load_sheet_data(sheet_data_path)
    import_master = load_import_master(import_master_path)
    
    # Process each category
    categories = ['sheets', 'records', 'music', 'import_master']
    
    print("\n2. SCANNING IMAGE DIRECTORIES...")
    for category in categories:
        images = find_images_by_category(images_dir, category)
        
        if images:
            print(f"\n3. ANALYZING {category.upper()} CATEGORY...")
            correction_map, unmatched = create_correction_mapping(
                sheet_data, import_master, images
            )
            
            print(f"   ✓ Matched: {len(correction_map)} images")
            print(f"   ⚠ Unmatched: {len(unmatched)} images")
            
            # Generate correction report for this category
            report_path = f'sheet_music_corrections_{category}.csv'
            generate_correction_report(correction_map, unmatched, report_path)
    
    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print("""
1. Review the generated correction reports:
   - sheet_music_corrections_sheets.csv
   - sheet_music_corrections_records.csv
   - sheet_music_corrections_music.csv

2. For each report:
   - "CORRECTED" entries: Verify titles match images correctly
   - "UNMATCHED - REVIEW REQUIRED": Manually verify these entries

3. Once verified, use these corrections to:
   - Update import_master.csv with corrected pairings
   - Rename/organize image files to match their metadata
   - Update Google Drive references with drive_file_ids

4. Test the corrected assignments before moving to production.
    """)

if __name__ == '__main__':
    main()
