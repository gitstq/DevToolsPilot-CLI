# DevToolsPilot-CLI

Lightweight Terminal Chrome DevTools Control Engine.

## Features

- CDP (Chrome DevTools Protocol) client via WebSocket
- Browser management (Chrome, Edge, Brave, Firefox)
- Page navigation, DOM manipulation, JavaScript execution
- Network traffic monitoring with HAR export
- Console log capture
- MCP (Model Context Protocol) server for AI integration
- Screenshot engine (viewport, full page, element)
- TUI dashboard with ANSI colors

## Installation

```bash
pip install -e .
# Optional: WebSocket support
pip install -e ".[websocket]"
```

## Usage

```bash
# Detect installed browsers
devtools-pilot detect

# Launch browser with remote debugging
devtools-pilot launch --browser chrome --port 9222

# Start MCP server
devtools-pilot mcp --port 9222

# Inspect page
devtools-pilot inspect --action info

# Take screenshot
devtools-pilot screenshot --type full

# Monitor network
devtools-pilot monitor --duration 60 --summary

# Execute JavaScript
devtools-pilot eval "document.title"
```

## Requirements

- Python 3.8+
- Chrome/Edge/Brave browser (for CDP features)

## License

MIT
