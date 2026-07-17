use std::env;
use std::path::Path;
use std::path::PathBuf;
use std::process::Command;
use std::process::Stdio;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SidecarRuntimeKind {
    ExternalExecutable,
    BundledExecutable,
    DevelopmentPython,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SidecarRuntime {
    pub kind: SidecarRuntimeKind,
    pub executable: PathBuf,
    pub arg_prefix: Vec<String>,
    pub current_dir: PathBuf,
    pub pythonpath: Option<String>,
    pub env_vars: Vec<(String, String)>,
}

impl SidecarRuntime {
    pub fn command(&self, args: &[String]) -> Command {
        let mut command = Command::new(&self.executable);
        command.args(&self.arg_prefix);
        command.args(args);
        command.current_dir(&self.current_dir);
        // Never inherit the parent console/stdin. A CUI child (console
        // PyInstaller / python.exe) would otherwise flash a terminal window
        // and share CTRL_CLOSE_EVENT with the desktop process.
        command.stdin(Stdio::null());
        if let Some(value) = &self.pythonpath {
            command.env("PYTHONPATH", value);
        }
        for (key, value) in &self.env_vars {
            command.env(key, value);
        }
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            // CREATE_NO_WINDOW: no console for the child; stdio pipes still work.
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            command.creation_flags(CREATE_NO_WINDOW);
        }
        command
    }
}

pub fn build_sidecar_command(
    args: &[String],
    resource_dir: Option<PathBuf>,
) -> Result<Command, String> {
    Ok(resolve_sidecar_runtime(resource_dir)?.command(args))
}

fn resolve_sidecar_runtime(resource_dir: Option<PathBuf>) -> Result<SidecarRuntime, String> {
    resolve_sidecar_runtime_with(
        resource_dir,
        PathBuf::from(env!("CARGO_MANIFEST_DIR")),
        |key| env::var(key).ok(),
        |path| path.exists(),
    )
}

fn resolve_sidecar_runtime_with<FEnv, FExists>(
    resource_dir: Option<PathBuf>,
    manifest_dir: PathBuf,
    env_var: FEnv,
    path_exists: FExists,
) -> Result<SidecarRuntime, String>
where
    FEnv: Fn(&str) -> Option<String>,
    FExists: Fn(&Path) -> bool,
{
    if let Some(raw_executable) =
        env_var("DWG_AUDIT_SIDECAR_EXE").filter(|value| !value.trim().is_empty())
    {
        let executable = PathBuf::from(raw_executable);
        if !path_exists(&executable) {
            return Err(format!(
                "DWG_AUDIT_SIDECAR_EXE points to a missing sidecar executable: {}",
                executable.display()
            ));
        }
        let current_dir = executable
            .parent()
            .map(Path::to_path_buf)
            .unwrap_or_else(|| manifest_dir.clone());
        let mut env_vars = packaging_env_vars(
            resource_dir.as_deref().or(Some(current_dir.as_path())),
            Some(executable.as_path()),
            &path_exists,
        );
        env_vars.push((
            "DWG_AUDIT_SIDECAR_EXE".to_string(),
            executable.to_string_lossy().to_string(),
        ));
        return Ok(SidecarRuntime {
            kind: SidecarRuntimeKind::ExternalExecutable,
            executable,
            arg_prefix: Vec::new(),
            current_dir,
            pythonpath: None,
            env_vars,
        });
    }

    if let Some(ref root) = resource_dir {
        for candidate in bundled_sidecar_candidates(root) {
            if path_exists(&candidate) {
                let mut env_vars = packaging_env_vars(
                    Some(root.as_path()),
                    Some(candidate.as_path()),
                    &path_exists,
                );
                env_vars.push((
                    "DWG_AUDIT_SIDECAR_EXE".to_string(),
                    candidate.to_string_lossy().to_string(),
                ));
                return Ok(SidecarRuntime {
                    kind: SidecarRuntimeKind::BundledExecutable,
                    current_dir: candidate
                        .parent()
                        .map(Path::to_path_buf)
                        .unwrap_or_else(|| root.clone()),
                    executable: candidate,
                    arg_prefix: Vec::new(),
                    pythonpath: None,
                    env_vars,
                });
            }
        }
    }

    if !development_source_fallback_enabled(&env_var) {
        return Err(
            "No bundled DWG audit sidecar executable was found. Package dwg-audit-sidecar with the app resources, set DWG_AUDIT_SIDECAR_EXE, or explicitly set DWG_AUDIT_ALLOW_SOURCE_FALLBACK=1 for a development-only source checkout fallback."
                .to_string(),
        );
    }

    let repo_root = resolve_repo_root(&manifest_dir, &env_var, &path_exists)?;
    let executable =
        PathBuf::from(env_var("DWG_AUDIT_PYTHON").unwrap_or_else(|| "python".to_string()));
    Ok(SidecarRuntime {
        kind: SidecarRuntimeKind::DevelopmentPython,
        executable,
        arg_prefix: vec!["-m".to_string(), "dwg_audit.cli".to_string()],
        current_dir: repo_root.clone(),
        pythonpath: Some(pythonpath_value(&repo_root, env_var("PYTHONPATH"))),
        env_vars: packaging_env_vars(resource_dir.as_deref(), None, &path_exists),
    })
}

fn packaging_env_vars<FExists>(
    resource_dir: Option<&Path>,
    sidecar_exe: Option<&Path>,
    path_exists: &FExists,
) -> Vec<(String, String)>
where
    FExists: Fn(&Path) -> bool,
{
    let mut env_vars = Vec::new();
    if let Some(root) = resource_dir {
        env_vars.push((
            "DWG_AUDIT_RESOURCE_DIR".to_string(),
            root.to_string_lossy().to_string(),
        ));
        if let Some(oda) = bundled_oda_executable(root, path_exists) {
            env_vars.push(("ODAFC_PATH".to_string(), oda.to_string_lossy().to_string()));
            env_vars.push((
                "DWG_AUDIT_BUNDLED_ODA_DIR".to_string(),
                oda.parent()
                    .unwrap_or(root)
                    .to_string_lossy()
                    .to_string(),
            ));
        }
    }
    if let Some(exe) = sidecar_exe {
        env_vars.push((
            "DWG_AUDIT_SIDECAR_DIR".to_string(),
            exe.parent()
                .unwrap_or(exe)
                .to_string_lossy()
                .to_string(),
        ));
    }
    env_vars
}

fn bundled_oda_executable<FExists>(resource_dir: &Path, path_exists: &FExists) -> Option<PathBuf>
where
    FExists: Fn(&Path) -> bool,
{
    let candidates = [
        resource_dir.join("oda").join("ODAFileConverter.exe"),
        resource_dir.join("oda").join("ODAFileConverter"),
        resource_dir
            .join("ODAFileConverter")
            .join("ODAFileConverter.exe"),
        resource_dir.join("ODAFileConverter.exe"),
    ];
    candidates.into_iter().find(|path| path_exists(path))
}

fn bundled_sidecar_candidates(resource_dir: &Path) -> Vec<PathBuf> {
    vec![
        resource_dir.join("dwg-audit-sidecar.exe"),
        resource_dir.join("dwg-audit-sidecar"),
        resource_dir.join("sidecar").join("dwg-audit-sidecar.exe"),
        resource_dir.join("sidecar").join("dwg-audit-sidecar"),
    ]
}

fn development_source_fallback_enabled<FEnv>(env_var: &FEnv) -> bool
where
    FEnv: Fn(&str) -> Option<String>,
{
    source_fallback_allowed(env_var, cfg!(debug_assertions))
}

fn source_fallback_allowed<FEnv>(env_var: &FEnv, debug_assertions: bool) -> bool
where
    FEnv: Fn(&str) -> Option<String>,
{
    debug_assertions
        || env_var("DWG_AUDIT_ALLOW_SOURCE_FALLBACK")
            .map(|value| value == "1")
            .unwrap_or(false)
}

fn resolve_repo_root<FEnv, FExists>(
    manifest_dir: &Path,
    env_var: &FEnv,
    path_exists: &FExists,
) -> Result<PathBuf, String>
where
    FEnv: Fn(&str) -> Option<String>,
    FExists: Fn(&Path) -> bool,
{
    if let Some(raw_root) = env_var("DWG_AUDIT_REPO_ROOT").filter(|value| !value.trim().is_empty())
    {
        let root = PathBuf::from(raw_root);
        if !path_exists(&root.join("src").join("dwg_audit")) {
            return Err(format!(
                "DWG_AUDIT_REPO_ROOT does not contain src/dwg_audit: {}",
                root.display()
            ));
        }
        return Ok(root);
    }

    let root = manifest_dir.join("../../..");
    if !path_exists(&root.join("src").join("dwg_audit")) {
        return Err(format!(
            "Unable to resolve a development DWG audit source tree from {}. Bundle a dwg-audit-sidecar executable or set DWG_AUDIT_REPO_ROOT.",
            manifest_dir.display()
        ));
    }
    Ok(root)
}

fn pythonpath_value(repo_root: &Path, existing: Option<String>) -> String {
    let separator = if cfg!(windows) { ";" } else { ":" };
    let mut parts = vec![repo_root.join("src").to_string_lossy().to_string()];
    if let Some(value) = existing.filter(|value| !value.trim().is_empty()) {
        parts.push(value);
    }
    parts.join(separator)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn external_sidecar_exe_takes_precedence() {
        let runtime = resolve_sidecar_runtime_with(
            Some(PathBuf::from("C:/app/resources")),
            PathBuf::from("C:/repo/apps/desktop/src-tauri"),
            |key| match key {
                "DWG_AUDIT_SIDECAR_EXE" => Some("C:/runtime/dwg-audit-sidecar.exe".to_string()),
                _ => None,
            },
            |path| path == Path::new("C:/runtime/dwg-audit-sidecar.exe"),
        )
        .expect("runtime should resolve");

        assert_eq!(runtime.kind, SidecarRuntimeKind::ExternalExecutable);
        assert_eq!(
            runtime.executable,
            PathBuf::from("C:/runtime/dwg-audit-sidecar.exe")
        );
        assert!(runtime.arg_prefix.is_empty());
        assert_eq!(runtime.current_dir, PathBuf::from("C:/runtime"));
        assert_eq!(runtime.pythonpath, None);
        assert!(runtime
            .env_vars
            .iter()
            .any(|(key, value)| key == "DWG_AUDIT_SIDECAR_EXE"
                && value == "C:/runtime/dwg-audit-sidecar.exe"));
    }

    #[test]
    fn bundled_sidecar_exe_beats_development_python() {
        let resource_root = PathBuf::from("C:/app/resources");
        let sidecar = resource_root
            .join("sidecar")
            .join("dwg-audit-sidecar.exe");
        let oda = resource_root.join("oda").join("ODAFileConverter.exe");
        let runtime = resolve_sidecar_runtime_with(
            Some(resource_root.clone()),
            PathBuf::from("C:/repo/apps/desktop/src-tauri"),
            |_| None,
            |path| path == sidecar.as_path() || path == oda.as_path(),
        )
        .expect("runtime should resolve");

        assert_eq!(runtime.kind, SidecarRuntimeKind::BundledExecutable);
        assert_eq!(runtime.executable, sidecar);
        assert!(runtime.arg_prefix.is_empty());
        assert_eq!(runtime.pythonpath, None);
        assert!(runtime.env_vars.iter().any(|(key, value)| {
            key == "DWG_AUDIT_RESOURCE_DIR" && value.as_str() == resource_root.to_string_lossy()
        }));
        assert!(runtime.env_vars.iter().any(|(key, value)| {
            key == "ODAFC_PATH" && value.as_str() == oda.to_string_lossy()
        }));
    }

    #[test]
    fn development_python_uses_repo_src_as_pythonpath() {
        let runtime = resolve_sidecar_runtime_with(
            None,
            PathBuf::from("C:/repo/apps/desktop/src-tauri"),
            |key| match key {
                "DWG_AUDIT_PYTHON" => Some("C:/Python/python.exe".to_string()),
                "DWG_AUDIT_ALLOW_SOURCE_FALLBACK" => Some("1".to_string()),
                "PYTHONPATH" => Some("C:/extra".to_string()),
                _ => None,
            },
            |path| path == Path::new("C:/repo/apps/desktop/src-tauri/../../../src/dwg_audit"),
        )
        .expect("runtime should resolve");

        let separator = if cfg!(windows) { ";" } else { ":" };
        assert_eq!(runtime.kind, SidecarRuntimeKind::DevelopmentPython);
        assert_eq!(runtime.executable, PathBuf::from("C:/Python/python.exe"));
        assert_eq!(runtime.arg_prefix, vec!["-m", "dwg_audit.cli"]);
        assert_eq!(
            runtime.pythonpath,
            Some(format!(
                "{}{}C:/extra",
                PathBuf::from("C:/repo/apps/desktop/src-tauri")
                    .join("../../..")
                    .join("src")
                    .to_string_lossy(),
                separator
            ))
        );
    }

    #[test]
    fn missing_runtime_reports_packaging_or_repo_fix() {
        let error = resolve_sidecar_runtime_with(
            Some(PathBuf::from("C:/app/resources")),
            PathBuf::from("C:/missing/apps/desktop/src-tauri"),
            |key| match key {
                "DWG_AUDIT_ALLOW_SOURCE_FALLBACK" => Some("1".to_string()),
                _ => None,
            },
            |_| false,
        )
        .expect_err("runtime should be missing");

        assert!(error.contains("Bundle a dwg-audit-sidecar executable"));
        assert!(error.contains("DWG_AUDIT_REPO_ROOT"));
    }

    #[test]
    fn release_policy_blocks_implicit_source_fallback() {
        assert!(!source_fallback_allowed(&|_| None, false));
        assert!(source_fallback_allowed(
            &|key| match key {
                "DWG_AUDIT_ALLOW_SOURCE_FALLBACK" => Some("1".to_string()),
                _ => None,
            },
            false,
        ));
    }
}
