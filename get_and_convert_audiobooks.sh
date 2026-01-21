#!/bin/bash

# Set up directories and filenames
SCRIPT_DIR=$(pwd)
EXPORT_DIR="$SCRIPT_DIR/AudibleExporter"
VENV_DIR="$EXPORT_DIR/venv"
AAX_SCRIPT="$EXPORT_DIR/AAXtoMP3"
AAX_REPO="https://github.com/KrumpetPirate/AAXtoMP3.git"

# Step 0a: Check for mp4art and install if missing
if ! command -v mp4art &> /dev/null; then
    echo "WARN: mp4art was not found in your PATH."
    echo "Without it, this script will not be able to add cover art to m4b files."
    
    # Attempt to install mp4art based on the OS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Attempting to install mp4v2 on macOS..."
        if command -v brew &> /dev/null; then
            brew install mp4v2
        else
            echo "Homebrew is not installed. Please install Homebrew and rerun the script."
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "Attempting to install mp4v2 on Ubuntu/Debian from source..."
        
        # Install dependencies for building mp4v2 from source
        sudo apt update
        sudo apt install -y build-essential cmake libtool pkg-config

        # Clone, build, and install mp4v2
        git clone https://github.com/enzo1982/mp4v2.git
        cd mp4v2
        cmake .
        make
        sudo make install
        cd ..
        rm -rf mp4v2

        # Add library path and update cache
        echo "/usr/local/lib" | sudo tee /etc/ld.so.conf.d/mp4v2.conf
        sudo ldconfig

        # Verify installation
        if ! command -v mp4art &> /dev/null; then
            echo "mp4art could not be installed. No cover art will be added to m4b files."
        else
            echo "mp4art successfully installed."
        fi
    else
        echo "Unsupported OS. Please manually install mp4v2 for your system."
        exit 1
    fi
else
    echo "mp4art is already installed."
fi

# Step 0b: Check for mediainfo and install if missing
if ! command -v mediainfo &> /dev/null; then
    echo "WARN: mediainfo was not found in your PATH."
    echo "Without it, this script will not be able to add narrator and description tags to m4b files."
    
    # Attempt to install mediainfo based on the OS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Attempting to install mediainfo on macOS..."
        if command -v brew &> /dev/null; then
            brew install mediainfo
        else
            echo "Homebrew is not installed. Please install Homebrew and rerun the script."
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "Attempting to install mediainfo on Ubuntu/Debian..."
        sudo apt update
        sudo apt install -y mediainfo

        # Verify installation
        if ! command -v mediainfo &> /dev/null; then
            echo "mediainfo could not be installed. No narrator or description tags will be added to m4b files."
        else
            echo "mediainfo successfully installed."
        fi
    else
        echo "Unsupported OS. Please manually install mediainfo for your system."
        exit 1
    fi
else
    echo "mediainfo is already installed."
fi

# Step 1: Create AudibleExporter directory if it doesn’t exist
if [ ! -d "$EXPORT_DIR" ]; then
    echo "Creating AudibleExporter directory..."
    mkdir -p $EXPORT_DIR
else
    echo "AudibleExporter directory already exists."
fi

# Navigate to AudibleExporter directory
cd $EXPORT_DIR

# Step 2: Create and activate virtual environment if it doesn’t already exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv $VENV_DIR
else
    echo "Virtual environment already exists."
fi
source $VENV_DIR/bin/activate

# Step 3: Install audible-cli in the virtual environment if not installed
if ! pip show audible-cli > /dev/null 2>&1; then
    echo "Installing audible-cli..."
    pip install --upgrade pip
    pip install audible-cli
else
    echo "audible-cli is already installed."
fi

# Step 4: Log into Audible (user interaction required if not logged in)
if [ ! -f "$HOME/.audible-cli/config" ]; then
    echo "Please log into your Audible account. This is a one-time setup."
    audible quickstart
else
    echo "Already logged into Audible."
fi

# Step 5: Always attempt to download audiobooks (re-download if files exist)
echo "Downloading audiobooks..."
audible download --aaxc --cover --cover-size 1215 --chapter --all

# Step 6: Retrieve activation bytes if not already retrieved
if [ -z "$ACTIVATION_BYTES" ]; then
    echo "Retrieving activation bytes..."
    # Capture the last 8 characters of the output
    ACTIVATION_BYTES=$(audible activation-bytes | tail -c 8)
    echo "Activation bytes: $ACTIVATION_BYTES"
else
    echo "Activation bytes already retrieved."
fi

# Step 7: Clone AAXtoMP3 repository to the parent directory, copy the script, and clean up if not already done
if [ ! -f "$AAX_SCRIPT" ]; then
    echo "Cloning AAXtoMP3 repository in the parent directory..."
    git clone $AAX_REPO ../AAXtoMP3
    echo "Copying AAXtoMP3 script and cleaning up..."

    # Move the AAXtoMP3 script into the AudibleExporter directory
    mv ../AAXtoMP3/AAXtoMP3 $AAX_SCRIPT
    rm -rf ../AAXtoMP3
else
    echo "AAXtoMP3 script already exists."
fi

# Step 8: Make the AAXtoMP3 script executable
chmod +x $AAX_SCRIPT

# Step 9: Always attempt to convert AAXC files to M4B format (even if files exist)
echo "Converting AAXC files to M4B format..."
bash $AAX_SCRIPT -e:m4b --use-audible-cli-data --authcode $ACTIVATION_BYTES *.aaxc

# Step 10: Deactivate virtual environment
echo "Deactivating virtual environment..."
deactivate

echo "Process complete. Audiobooks have been downloaded and converted."