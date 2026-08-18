#!/usr/bin/env python3
import os
from ADA.skills.photos.organize_photos import run as organize_run

def main():
    folder = 'ADA/test_photos'
    if not os.path.isdir(folder):
        print('Test folder not found:', folder)
        return
    res = organize_run({'dir': folder})
    print('Organize result:', res)

if __name__ == '__main__':
    main()
