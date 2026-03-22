#!/usr/bin/env python3
"""
Migration script to add is_verified column to the users table.
Run this script once to add the blue tick verification feature.

Usage: python migrate_add_verified.py
"""

import sqlite3
import os

def migrate():
    # Get the database path
    db_path = os.path.join('instance', 'sns_mail.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        print("The column will be created automatically when you start the app.")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_verified' in columns:
            print("Column 'is_verified' already exists in users table.")
        else:
            # Add the is_verified column
            cursor.execute("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 0")
            conn.commit()
            print("Successfully added 'is_verified' column to users table.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    migrate()