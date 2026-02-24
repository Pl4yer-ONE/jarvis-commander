#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║     JARVIS — INSTALL AUTO-START SERVICE                     ║
# ╚══════════════════════════════════════════════════════════════╝
#
# This script installs Jarvis as a systemd user service that
# starts automatically when you log in.
#
# Usage: ./install_service.sh
#
set -e

CYAN='\033[36m'
GREEN='\033[32m'
YELLOW='\033[33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/jarvis.service"
USER_SERVICE_DIR="$HOME/.config/systemd/user"

echo -e "${CYAN}Installing Jarvis auto-start service...${NC}"

# ── Step 1: Install desktop control dependencies ────────────
echo -e "${YELLOW}[1/4]${NC} Installing desktop control tools..."
sudo apt install -y xdotool libnotify-bin xclip brightnessctl wmctrl 2>/dev/null || {
    echo -e "${YELLOW}  ⚠ Some packages may have failed. Non-critical.${NC}"
}

# ── Step 2: Install PyAudio + Whisper if missing ────────────
echo -e "${YELLOW}[2/4]${NC} Ensuring Python dependencies..."
cd "$SCRIPT_DIR"
source venv/bin/activate
pip install -q PyAudio openai-whisper 2>/dev/null || true

# ── Step 3: Copy service file ───────────────────────────────
echo -e "${YELLOW}[3/4]${NC} Installing systemd user service..."
mkdir -p "$USER_SERVICE_DIR"
cp "$SERVICE_FILE" "$USER_SERVICE_DIR/jarvis.service"

# Reload systemd user daemon
systemctl --user daemon-reload

# Enable auto-start on login
systemctl --user enable jarvis.service

echo -e "${GREEN}  ✅ Service installed and enabled.${NC}"

# ── Step 4: Start it now ────────────────────────────────────
echo -e "${YELLOW}[4/4]${NC} Starting Jarvis service now..."
systemctl --user start jarvis.service

sleep 2
STATUS=$(systemctl --user is-active jarvis.service 2>/dev/null || echo "unknown")

if [ "$STATUS" = "active" ]; then
    echo -e "${GREEN}  ✅ Jarvis is running!${NC}"
else
    echo -e "${YELLOW}  ⚠ Service status: $STATUS. Check logs with:${NC}"
    echo -e "    journalctl --user -u jarvis.service -f"
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Jarvis is installed as an auto-start service!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}Control commands:${NC}"
echo -e "    ${CYAN}systemctl --user status jarvis${NC}   # Check status"
echo -e "    ${CYAN}systemctl --user restart jarvis${NC}  # Restart"
echo -e "    ${CYAN}systemctl --user stop jarvis${NC}     # Stop"
echo -e "    ${CYAN}systemctl --user disable jarvis${NC}  # Disable auto-start"
echo -e "    ${CYAN}journalctl --user -u jarvis -f${NC}   # View live logs"
echo ""
