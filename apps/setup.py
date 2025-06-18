#!/usr/bin/env python3
"""
CheckMate Setup Script
Run this script to quickly set up the CheckMate application.
"""

import os
import sys
import subprocess

def run_command(command, description):
    """Run a command and handle errors."""
    print(f"\n📋 {description}...")
    try:
        subprocess.run(command, shell=True, check=True)
        print(f"✅ {description} completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during {description}: {e}")
        return False
    return True

def main():
    print("🎯 Welcome to CheckMate Setup!")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        return
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Setup steps
    steps = [
        ("pip install -r requirements.txt", "Installing dependencies"),
        ("python manage.py makemigrations", "Creating database migrations"),
        ("python manage.py migrate", "Setting up database"),
        ("python manage.py collectstatic --noinput", "Collecting static files"),
    ]
    
    for command, description in steps:
        if not run_command(command, description):
            print("\n💥 Setup failed! Please check the error above.")
            return
    
    print("\n🎉 Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Create a superuser: python manage.py createsuperuser")
    print("2. Start the server: python manage.py runserver")
    print("3. Visit: http://127.0.0.1:8000")
    print("\n✨ Happy testing with CheckMate!")

if __name__ == "__main__":
    main()