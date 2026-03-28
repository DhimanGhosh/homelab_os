When you ran python3 bootstrap.py, it created a local virtual environment in .venv, upgraded pip/setuptools/wheel, then installed the project itself in editable mode with pip install -e .... That is why you see package install output and then the final message telling you the next commands to run.

When you ran source .venv/bin/activate, you switched your shell to use that project-specific Python environment, so homelabctl points to this project’s code and dependencies instead of the system Python.

When you ran homelabctl bootstrap-host --env-file .env, it performed the host-side setup and completed successfully. In practice, this command is meant to prepare the machine-level pieces the framework depends on, such as directories, service wiring, Caddy/Docker-related setup, and recovery integration. The important part from your output is that it finished cleanly with Host bootstrap completed.

Now, how to change CC or any app and build/install directly from CLI:

1. Edit the Control Center

For CC UI/backend changes, work mainly in:

homelab_platform/web.py
homelab_platform/templates/index.html
homelab_platform/static/css/style.css
homelab_platform/static/js/app.js

Typical examples:

change dashboard layout → templates/index.html
change styles → static/css/style.css
change upload/install/remove button behavior → static/js/app.js
change backend routes/API behavior → web.py

2. Edit any app bundle

For any app, edit its source under:

bundle_specs/<bundle-name>/

Examples:

bundle_specs/dictionary.app.v1.4.5/
bundle_specs/pihole.app.v1.2.5/
bundle_specs/control_center_bundle_v1_6_7/

Inside each bundle, the important files are usually:

metadata.json → app id, version, ports, URLs
bundle.py → Python install/uninstall entrypoint
runtime/docker-compose.yml → runtime container definition
optionally app files/assets if that bundle contains them

3. Build one bundle from CLI

After editing a bundle, build it into a .tgz:

source .venv/bin/activate

homelabctl build-bundle \
  --source-dir bundle_specs/dictionary.app.v1.4.5 \
  --output-path dist/dictionary.app.v1.4.5.tgz

4. Build all bundles from CLI

If you changed multiple bundles:

source .venv/bin/activate
homelabctl build-all-bundles --env-file .env

That regenerates the .tgz files inside dist/.

5. Install a bundle directly from CLI

Once the .tgz exists, install it like this:

source .venv/bin/activate
homelabctl install-bundle --bundle dist/dictionary.app.v1.4.5.tgz --env-file .env

Because CLI and UI share the same install state, a CLI-installed bundle should also show up in the UI.

6. Remove an installed app from CLI
source .venv/bin/activate
homelabctl remove-app --app-id dictionary --env-file .env

7. Trigger the integrated recovery from CLI

If CC/Pi-hole/Caddy/DNS gets disturbed:

source .venv/bin/activate
homelabctl recover-stack --env-file .env

8. Check framework settings from CLI
source .venv/bin/activate
homelabctl show-settings --env-file .env

9. List built bundles from CLI
source .venv/bin/activate
homelabctl list-bundles --env-file .env
Practical workflow you should follow

For changing an app:

cd ~/raspi_homelab_python_framework
source .venv/bin/activate

# edit files
nano bundle_specs/dictionary.app.v1.4.5/metadata.json
nano bundle_specs/dictionary.app.v1.4.5/bundle.py
nano bundle_specs/dictionary.app.v1.4.5/runtime/docker-compose.yml

# rebuild
homelabctl build-bundle \
  --source-dir bundle_specs/dictionary.app.v1.4.5 \
  --output-path dist/dictionary.app.v1.4.5.tgz

# install
homelabctl install-bundle --bundle dist/dictionary.app.v1.4.5.tgz --env-file .env

For changing CC:

cd ~/raspi_homelab_python_framework
source .venv/bin/activate

nano homelab_platform/web.py
nano homelab_platform/templates/index.html
nano homelab_platform/static/css/style.css
nano homelab_platform/static/js/app.js

Then either:

restart the framework CC service if you are using the framework-managed CC, or
build/install the CC bundle if you want the update to travel as a .tgz.

A safe CC bundle rebuild flow would be:

homelabctl build-bundle \
  --source-dir bundle_specs/control_center_bundle_v1_6_7 \
  --output-path dist/control_center_bundle_v1_6_7.tgz

Then install it either:

from CLI with homelabctl install-bundle ...
or upload that same .tgz in the UI
Very important rule

On your live Pi, do not let the new Python framework bind directly to 8444. Your stable setup is:

Caddy -> :8444
Control Center backend -> 127.0.0.1:9000

So for maintenance:

edit CC/app code
build .tgz
install via CLI or UI
let Caddy continue owning 8444
