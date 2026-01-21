import os
import shutil

# Define Paths
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))  # Root directory
AUDIOBOOKS_DIR = os.path.join(ROOT_DIR, "Audiobooks")  # Old location
M4B_DIR = os.path.join(ROOT_DIR, "M4B")  # New structured folder

# Ensure M4B directory exists
os.makedirs(M4B_DIR, exist_ok=True)

def move_m4b_files():
    print("🚀 Moving M4B files into structured folders...")
    for author in os.listdir(AUDIOBOOKS_DIR):
        author_path = os.path.join(AUDIOBOOKS_DIR, author)

        if os.path.isdir(author_path):
            for title in os.listdir(author_path):
                title_path = os.path.join(author_path, title)
                
                if os.path.isdir(title_path):
                    # Find M4B file inside the title folder
                    for file in os.listdir(title_path):
                        if file.endswith(".m4b"):
                            new_author_path = os.path.join(M4B_DIR, author)
                            new_title_path = os.path.join(new_author_path, title)

                            os.makedirs(new_title_path, exist_ok=True)

                            old_file_path = os.path.join(title_path, file)
                            new_file_path = os.path.join(new_title_path, file)

                            shutil.move(old_file_path, new_file_path)
                            print(f"✅ Moved: {file} → {new_file_path}")

    print("🎧 M4B organization complete!")

if __name__ == "__main__":
    move_m4b_files()