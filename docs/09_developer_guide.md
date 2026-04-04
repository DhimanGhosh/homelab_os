
# Developer Guide

## Add a new plugin
1. create `plugins/<plugin_name>/`
2. add `plugin.json`
3. add backend/frontend/docker/assets/migrations folders
4. implement `install.py`, `uninstall.py`, `upgrade.py`
5. run `homelabctl build-plugin`

## Coding style
- keep HTML, CSS, and JS separate
- do not hardcode app name/version in HTML
- use manifest metadata and API-provided values
- prefer readable code over minified one-line assets
