# Findings

- Remote: `origin` is `https://github.com/sallowayma-git/XJCheck.git`.
- Branch: `master`; local and remote currently point to `0162322`.
- Build entrypoint: `apps/desktop/scripts/build-windows-release.ps1 -Clean`, also exposed as `npm run package:windows`.
- Expected installer: `apps/desktop/src-tauri/target/release/bundle/nsis/DWG Audit Desktop_*_x64-setup.exe`.
- Tauri bundle uses NSIS `currentUser`; no tracked overlay-install script exists.
