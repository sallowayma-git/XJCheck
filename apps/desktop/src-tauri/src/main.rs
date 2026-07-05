use std::env;
use std::fs;
use std::io::BufRead;
use std::io::BufReader;
use std::io::Read;
use std::path::PathBuf;
use std::process::Command;
use std::process::Stdio;

use serde_json::json;
use serde_json::Value;
use tauri::AppHandle;
use tauri::Emitter;

const DESKTOP_EVENT_NAME: &str = "dwg-audit://sidecar-event";

#[tauri::command]
fn desktop_analyze_session(
    app: AppHandle,
    input_root: String,
    session_id: Option<String>,
) -> Result<Value, String> {
    let workspace_root = default_workspace_root()?;
    let state_db = default_state_db_path()?;
    let mut args = vec![
        "-m".to_string(),
        "dwg_audit.cli".to_string(),
        "analyze-session".to_string(),
        "--input".to_string(),
        input_root,
        "--workspace-root".to_string(),
        workspace_root.to_string_lossy().to_string(),
        "--state-db".to_string(),
        state_db.to_string_lossy().to_string(),
    ];
    if let Some(value) = session_id {
        args.push("--session-id".to_string());
        args.push(value);
    }

    let mut child = build_python_command(&args)?
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| format!("Failed to start Python sidecar: {error}"))?;

    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "Python sidecar stdout pipe is unavailable.".to_string())?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| "Python sidecar stderr pipe is unavailable.".to_string())?;

    let mut run_result: Option<Value> = None;
    for line in BufReader::new(stdout).lines() {
        let line = line.map_err(|error| format!("Failed to read sidecar output: {error}"))?;
        if line.trim().is_empty() {
            continue;
        }
        let payload: Value =
            serde_json::from_str(&line).map_err(|error| format!("Failed to parse sidecar JSON line: {error}; line={line}"))?;
        if payload.get("event").and_then(Value::as_str) == Some("run_result") {
            run_result = Some(payload);
            continue;
        }
        app.emit(DESKTOP_EVENT_NAME, &payload)
            .map_err(|error| format!("Failed to emit sidecar event: {error}"))?;
    }

    let status = child
        .wait()
        .map_err(|error| format!("Failed to wait for Python sidecar: {error}"))?;
    let mut stderr_text = String::new();
    BufReader::new(stderr)
        .read_to_string(&mut stderr_text)
        .map_err(|error| format!("Failed to read Python sidecar stderr: {error}"))?;

    if !status.success() {
        let detail = stderr_text.trim();
        return Err(if detail.is_empty() {
            format!("Python sidecar exited with status {status}.")
        } else {
            format!("Python sidecar exited with status {status}: {detail}")
        });
    }

    let result = run_result.ok_or_else(|| "Python sidecar did not emit a final run_result record.".to_string())?;
    Ok(json!({
        "projects": result.get("projects").cloned().unwrap_or(Value::Array(Vec::new()))
    }))
}

#[tauri::command]
fn desktop_list_recent_projects() -> Result<Value, String> {
    let state_db = default_state_db_path()?;
    let payload = run_python_json_owned(vec![
        "-m".to_string(),
        "dwg_audit.cli".to_string(),
        "list-recent-projects".to_string(),
        "--state-db".to_string(),
        state_db.to_string_lossy().to_string(),
    ])?;
    Ok(payload.get("projects").cloned().unwrap_or(Value::Array(Vec::new())))
}

#[tauri::command]
fn desktop_load_result(project_id: String) -> Result<Value, String> {
    let state_db = default_state_db_path()?;
    run_python_json_owned(vec![
        "-m".to_string(),
        "dwg_audit.cli".to_string(),
        "load-result".to_string(),
        "--project-id".to_string(),
        project_id,
        "--state-db".to_string(),
        state_db.to_string_lossy().to_string(),
    ])
}

#[tauri::command]
fn desktop_render_preview(
    project_id: String,
    issue_id: Option<String>,
    sheet_id: Option<String>,
) -> Result<Value, String> {
    let state_db = default_state_db_path()?;
    let mut args = vec![
        "-m".to_string(),
        "dwg_audit.cli".to_string(),
        "render-preview".to_string(),
        "--project-id".to_string(),
        project_id,
        "--state-db".to_string(),
        state_db.to_string_lossy().to_string(),
    ];
    if let Some(value) = issue_id {
        args.push("--issue-id".to_string());
        args.push(value);
    }
    if let Some(value) = sheet_id {
        args.push("--sheet-id".to_string());
        args.push(value);
    }
    run_python_json_owned(args)
}

#[tauri::command]
fn desktop_set_issue_status(
    project_id: String,
    issue_id: String,
    status: String,
) -> Result<Value, String> {
    let state_db = default_state_db_path()?;
    run_python_json_owned(vec![
        "-m".to_string(),
        "dwg_audit.cli".to_string(),
        "set-issue-status".to_string(),
        "--project-id".to_string(),
        project_id,
        "--issue-id".to_string(),
        issue_id,
        "--status".to_string(),
        status,
        "--state-db".to_string(),
        state_db.to_string_lossy().to_string(),
    ])
}

fn run_python_json_owned(args: Vec<String>) -> Result<Value, String> {
    let output = build_python_command(&args)?
        .output()
        .map_err(|error| format!("Failed to execute Python CLI: {error}"))?;
    if !output.status.success() {
        let detail = String::from_utf8_lossy(&output.stderr).trim().to_string();
        return Err(if detail.is_empty() {
            format!("Python CLI exited with status {}.", output.status)
        } else {
            format!("Python CLI exited with status {}: {}", output.status, detail)
        });
    }
    let stdout = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(&stdout).map_err(|error| format!("Failed to parse Python CLI JSON output: {error}"))
}

fn build_python_command(args: &[String]) -> Result<Command, String> {
    let repo_root = resolve_repo_root()?;
    let python_path = pythonpath_value(&repo_root)?;
    let executable = env::var("DWG_AUDIT_PYTHON").unwrap_or_else(|_| "python".to_string());

    let mut command = Command::new(executable);
    command.args(args);
    command.current_dir(&repo_root);
    command.env("PYTHONPATH", python_path);
    Ok(command)
}

fn resolve_repo_root() -> Result<PathBuf, String> {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../..")
        .canonicalize()
        .map_err(|error| format!("Failed to resolve repository root: {error}"))
}

fn pythonpath_value(repo_root: &PathBuf) -> Result<String, String> {
    let src_dir = repo_root.join("src");
    let mut parts = vec![src_dir.to_string_lossy().to_string()];
    if let Ok(existing) = env::var("PYTHONPATH") {
        if !existing.trim().is_empty() {
            parts.push(existing);
        }
    }
    Ok(parts.join(";"))
}

fn default_workspace_root() -> Result<PathBuf, String> {
    let root = default_local_app_data_dir()?.join("dwg-audit").join("sessions");
    fs::create_dir_all(&root).map_err(|error| format!("Failed to create workspace root {}: {error}", root.display()))?;
    Ok(root)
}

fn default_state_db_path() -> Result<PathBuf, String> {
    let db_path = default_local_app_data_dir()?.join("dwg-audit").join("desktop_state.db");
    if let Some(parent) = db_path.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("Failed to create state DB directory {}: {error}", parent.display()))?;
    }
    Ok(db_path)
}

fn default_local_app_data_dir() -> Result<PathBuf, String> {
    if let Ok(value) = env::var("LOCALAPPDATA") {
        let path = PathBuf::from(value);
        if !path.as_os_str().is_empty() {
            return Ok(path);
        }
    }
    Err("LOCALAPPDATA is unavailable; cannot resolve desktop workspace paths.".to_string())
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            desktop_analyze_session,
            desktop_list_recent_projects,
            desktop_load_result,
            desktop_render_preview,
            desktop_set_issue_status
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
