import os

bot_folders = ['bot_2', 'bot_3', 'bot_4', 'bot_5', 'bot_6', 'bot_7']
for b in bot_folders:
    app_path = os.path.join(b, 'app.py')
    if os.path.exists(app_path):
        print("="*80)
        print(f"BOT FOLDER: {b} -> {app_path}")
        print("="*80)
        with open(app_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            for i, line in enumerate(lines[:60]):
                print(f"{i+1}: {line.rstrip()}")
