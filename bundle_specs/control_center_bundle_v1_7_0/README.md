# control_center_bundle_v1_7_0

This bundle redesign makes the Control Center behave like the other app bundles during `build-all-bundles`.

## Design
- The authoritative Control Center source still lives in `homelab_platform/`.
- During bundle build, `BundleBuilder` materializes a `payload/` directory inside this bundle spec.
- That payload contains the files required to update the live Control Center repo.
- `install-bundle` for this bundle uses the custom `bundle.py` in this folder, so it does **not** require `runtime/docker-compose.yml`.

## Why this is better
- The repo now has a visible Control Center bundle spec like the other apps.
- `homelabctl build-all-bundles` can produce a valid Control Center TGZ.
- `homelabctl install-bundle --bundle dist/control_center_bundle_v1_7_0.tgz --env-file .env` no longer fails with the missing runtime error.
