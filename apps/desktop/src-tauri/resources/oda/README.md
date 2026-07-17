# Bundled ODA File Converter resources

This directory is mapped into the installed app as `oda/` by Tauri.

## How to stage (do not commit binaries)

```powershell
# Auto-discover a local ODA install / ODAFC_PATH
.pps\desktop\scripts\stage-oda-resources.ps1 -Clean

# Or point at an explicit install directory
.pps\desktop\scripts\stage-oda-resources.ps1 -SourceDir "C:\Program Files\ODA\ODAFileConverter 27.1.0" -Clean
```

Expected layout after staging:

```
resources/oda/
  ODAFileConverter.exe
  *.dll / *.tx / Qt runtime files
  PACKAGED_FROM.txt
  README.md
```

## Runtime discovery order

1. Config `ingest.odafc_path` (optional override)
2. `ODAFC_PATH` / `ODA_FILE_CONVERTER` (desktop shell injects these for the bundled path)
3. Bundled resource layouts under `DWG_AUDIT_RESOURCE_DIR` / sidecar sibling `oda/`
4. `PATH`
5. Versioned Windows Program Files installs

Binary ODA payloads must stay out of git. Only this README (and empty layout markers) are tracked.
