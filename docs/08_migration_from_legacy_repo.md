
# Migration from Legacy Repo

## Removed legacy roots
- `homelab_platform/`
- `bundle_specs/`

## New homes
- legacy service code -> `core/services/`
- legacy bundle handling -> `core/plugin_manager/`
- legacy bundle specs -> `plugins/`
- legacy metadata -> `plugin.json`
- legacy dist artifacts -> `build/`

## Plugin directory mapping

Examples:
- `music-player.app.v7.1.2/` -> `plugins/music_player/`
- `link-downloader.app.v1.0.9/` -> `plugins/link_downloader/`
- `control-center.app.v1.7.1/` -> `plugins/control_center/`
