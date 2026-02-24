#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║           JARVIS AI ASSISTANT — ONE-CLICK SETUP             ║
# ╚══════════════════════════════════════════════════════════════╝
#
# Run this script to install all system dependencies:
#   chmod +x setup.sh && ./setup.sh
#
set -e

CYAN='\033[36m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
NC='\033[0m'

echo -e "${CYAN}"
echo "     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗"
echo "     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝"
echo "     ██║███████║██████╔╝██║   ██║██║███████╗"
echo "██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║"
echo "╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║"
echo " ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝"
echo -e "${NC}"
echo -e "${YELLOW}  Setting up your Jarvis AI Assistant...${NC}"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Step 1: System audio dependencies ────────────────────────
echo -e "${CYAN}[1/5]${NC} Installing system audio dependencies..."
sudo apt update -qq
sudo apt install -y portaudio19-dev python3-pyaudio espeak espeak-ng libespeak-dev
echo -e "${GREEN}  ✅ Audio dependencies installed.${NC}"

# ── Step 2: Install Ollama ───────────────────────────────────
echo ""
echo -e "${CYAN}[2/5]${NC} Installing Ollama (local LLM runtime)..."
if command -v ollama &> /dev/null; then
    echo -e "${GREEN}  ✅ Ollama already installed.${NC}"
else
    curl -fsSL https://ollama.ai/install.sh | sh
    echo -e "${GREEN}  ✅ Ollama installed.${NC}"
fi

# ── Step 3: Pull the LLM model ──────────────────────────────
echo ""
echo -e "${CYAN}[3/5]${NC} Pulling Mistral 7B model (~4.4 GB download)..."
echo -e "${YELLOW}  This may take a few minutes on the first run.${NC}"
ollama pull mistral:7b-instruct-v0.3-q4_K_M
echo -e "${GREEN}  ✅ Model ready.${NC}"

# ── Step 4: Python virtual environment ──────────────────────
echo ""
echo -e "${CYAN}[4/5]${NC} Setting up Python environment..."
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt
pip install -q PyAudio openai-whisper
echo -e "${GREEN}  ✅ Python dependencies installed.${NC}"

# ── Step 5: Verify ──────────────────────────────────────────
echo ""
echo -e "${CYAN}[5/5]${NC} Verifying installation..."
python3 -c "
import sys; sys.path.insert(0, '.')
from config import load_config; load_config()
from skills import SkillRegistry
r = SkillRegistry(); r.discover()
print(f'  Config: OK | Skills: {len(r.list_skills())} loaded')
print(f'  Time test: {r.execute(\"get_time\", {})}')
" 2>&1

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ Jarvis is ready!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Run Jarvis with:"
echo -e "    ${CYAN}cd ${SCRIPT_DIR}${NC}"
echo -e "    ${CYAN}source venv/bin/activate${NC}"
echo -e "    ${CYAN}python main.py --text${NC}      # text mode (test first)"
echo -e "    ${CYAN}python main.py${NC}             # voice mode"
echo -e "    ${CYAN}python main.py --always-listen${NC}  # hands-free mode"
echo ""
