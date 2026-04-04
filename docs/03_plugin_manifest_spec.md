{
  "id": "voice-ai",
  "name": "Voice AI",
  "version": "1.3.3",
  "category": "ai",
  "entrypoint": {
    "type": "web",
    "path": "/plugins/voice-ai/"
  },
  "backend": {
    "framework": "flask",
    "module": "backend.app:create_app"
  },
  "ui": {
    "title": "Voice AI",
    "icon": "assets/icon.png",
    "mobile_safe": true
  },
  "network": {
    "internal_port": 8124,
    "public_port": 8452,
    "proxy": true
  },
  "capabilities": [
    "audio.capture",
    "audio.playback",
    "network.outbound"
  ],
  "healthcheck": {
    "path": "http://127.0.0.1:8124/config/client",
    "interval_seconds": 30
  },
  "lifecycle": {
    "install": "python install.py",
    "uninstall": "python uninstall.py",
    "upgrade": "python upgrade.py"
  }
}