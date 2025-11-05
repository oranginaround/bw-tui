# bw-tui

A minimal console password manager that wraps the Bitwarden CLI in a curses-based terminal interface.

## Features

- Browse your Bitwarden vault in a terminal interface
- Search for vault items by name or username
- Copy passwords to clipboard with a single keystroke
- Secure master password entry
- Lightweight and fast

## Prerequisites

1. **Bitwarden CLI**: You need to have the Bitwarden CLI installed:
   ```bash
   npm install -g @bitwarden/cli
   ```

2. **Python 3.8+**: The application requires Python 3.8 or later.

3. **Clipboard Tools** (optional, for password copying):
   
   **On Debian/Ubuntu:**
   ```bash
   sudo apt install xclip
   # or
   sudo apt install xsel
   ```
   
   **On Wayland systems:**
   ```bash
   sudo apt install wl-clipboard
   ```
   
   **On macOS:**
   ```bash
   # No additional installation needed
   ```
   
   If no clipboard tools are available, passwords will be displayed on screen instead.

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/bw-tui.git
   cd bw-tui
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Make sure you're logged in to Bitwarden CLI:
   ```bash
   bw login
   ```

## Usage

Run the application:
```bash
python main.py
```

### Keyboard Controls

- **Arrow Keys**: Navigate through items
- **s** or **/**: Start searching
- **c** or **Enter**: Copy password to clipboard
- **ESC**: Clear search / Return to browse mode
- **q**: Quit application

### First Run

On first run, you'll be prompted to enter your Bitwarden master password to unlock your vault. The application will then display your vault items in a list format.

## Security

- Passwords are only temporarily held in memory during clipboard operations
- The application uses the official Bitwarden CLI for all vault operations
- No passwords are stored locally by this application

## Development

### Project Structure

```
bw-tui/
├── bw_tui/
│   ├── __init__.py
│   ├── app.py          # Main application class
│   ├── bitwarden.py    # Bitwarden CLI wrapper
│   └── ui.py           # Curses UI components
├── main.py             # Entry point
├── requirements.txt    # Python dependencies
├── pyproject.toml      # Project configuration
└── README.md          # This file
```

### Running in Debug Mode

To enable debug logging, set the environment variable:
```bash
BW_DEBUG=1 python main.py
```

Debug logs will be written to `bw-tui.log`.

## License

MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Known Issues

- Clipboard functionality requires a display server (X11, Wayland, etc.)
- Some terminal emulators may not support all key combinations

## Roadmap

- [ ] Support for TOTP codes
- [ ] Folder organization
- [ ] Item creation/editing
- [ ] Secure notes support
- [ ] Configuration file support