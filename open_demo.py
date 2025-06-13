#!/usr/bin/env python3
"""
Open Demo HTML - Simple script to open the Datasheet AI Comparison System demo
"""

import webbrowser
import os
import sys

def open_demo():
    """Open the demo.html file in the default web browser"""
    try:
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Path to the demo.html file
        demo_file = os.path.join(script_dir, "demo.html")
        
        # Check if the file exists
        if not os.path.exists(demo_file):
            print(f"Error: Could not find {demo_file}")
            print("Make sure the demo.html file is in the same directory as this script.")
            return False
        
        # Convert file path to URL format
        file_url = f"file://{os.path.abspath(demo_file)}"
        
        # Open the URL in the default browser
        print(f"Opening Datasheet AI Comparison System demo in your browser...")
        webbrowser.open(file_url)
        
        print("If the browser doesn't open automatically, you can manually open this file:")
        print(demo_file)
        
        return True
    
    except Exception as e:
        print(f"Error opening demo: {e}")
        return False

if __name__ == "__main__":
    open_demo()
