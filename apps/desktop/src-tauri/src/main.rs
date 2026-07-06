use std::env;
use std::fs;
use std::io::BufRead;
use std::io::BufReader;
use std::io::Read;
use std::path::PathBuf;
use std::process::Stdio;

use serde_json::json;
use serde_json::Value;
use tauri::AppHandle;
use tauri::Emitter;
use tauri::Manager;

mod sidecar_runtime;

use sidecar_runtime::build_sidecar_command;

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

    let mut child = build_desktop_sidecar_command(&app, &args)?
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| format!("Failed to start DWG audit sidecar: {error}"))?;

    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "DWG audit sidecar stdout pipe is unavailable.".to_string())?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| "DWG audit sidecar stderr pipe is unavailable.".to_string())?;

    let mut run_result: Option<Value> = None;
    for line in BufReader::new(stdout).lines() {
        let line = line.map_err(|error| format!("Failed to read sidecar output: {error}"))?;
        if line.trim().is_empty() {
            continue;
        }
        let payload: Value = serde_json::from_str(&line)
            .map_err(|error| format!("Failed to parse sidecar JSON line: {error}; line={line}"))?;
        if payload.get("event").and_then(Value::as_str) == Some("run_result") {
            run_result = Some(payload);
            continue;
        }
        app.emit(DESKTOP_EVENT_NAME, &payload)
            .map_err(|error| format!("Failed to emit sidecar event: {error}"))?;
    }

    let status = child
        .wait()
        .map_err(|error| format!("Failed to wait for DWG audit sidecar: {error}"))?;
    let mut stderr_text = String::new();
    BufReader::new(stderr)
        .read_to_string(&mut stderr_text)
        .map_err(|error| format!("Failed to read DWG audit sidecar stderr: {error}"))?;

    if !status.success() {
        let detail = stderr_text.trim();
        return Err(if detail.is_empty() {
            format!("DWG audit sidecar exited with status {status}.")
        } else {
            format!("DWG audit sidecar exited with status {status}: {detail}")
        });
    }

    let result = run_result
        .ok_or_else(|| "DWG audit sidecar did not emit a final run_result record.".to_string())?;
    Ok(json!({
        "projects": result.get("projects").cloned().unwrap_or(Value::Array(Vec::new()))
    }))
}

#[tauri::command]
fn desktop_list_recent_projects(app: AppHandle) -> Result<Value, String> {
    let state_db = default_state_db_path()?;
    let payload = run_sidecar_json_owned(
        &app,
        vec![
            "list-recent-projects".to_string(),
            "--state-db".to_string(),
            state_db.to_string_lossy().to_string(),
        ],
    )?;
    Ok(payload
        .get("projects")
        .cloned()
        .unwrap_or(Value::Array(Vec::new())))
}

#[tauri::command]
fn desktop_load_result(app: AppHandle, project_id: String) -> Result<Value, String> {
    let state_db = default_state_db_path()?;
    run_sidecar_json_owned(
        &app,
        vec![
            "load-result".to_string(),
            "--project-id".to_string(),
            project_id,
            "--state-db".to_string(),
            state_db.to_string_lossy().to_string(),
        ],
    )
}

#[tauri::command]
fn desktop_render_preview(
    app: AppHandle,
    project_id: String,
    issue_id: Option<String>,
    sheet_id: Option<String>,
    line_group_id: Option<String>,
) -> Result<Value, String> {
    let state_db = default_state_db_path()?;
    let mut args = vec![
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
    if let Some(value) = line_group_id {
        args.push("--line-group-id".to_string());
        args.push(value);
    }
    run_sidecar_json_owned(&app, args)
}

#[tauri::command]
fn desktop_set_issue_status(
    app: AppHandle,
    project_id: String,
    issue_id: String,
    status: String,
) -> Result<Value, String> {
    let state_db = default_state_db_path()?;
    run_sidecar_json_owned(
        &app,
        vec![
            "set-issue-status".to_string(),
            "--project-id".to_string(),
            project_id,
            "--issue-id".to_string(),
            issue_id,
            "--status".to_string(),
            status,
            "--state-db".to_string(),
            state_db.to_string_lossy().to_string(),
        ],
    )
}

fn run_sidecar_json_owned(app: &AppHandle, args: Vec<String>) -> Result<Value, String> {
    let output = build_desktop_sidecar_command(app, &args)?
        .output()
        .map_err(|error| format!("Failed to execute DWG audit sidecar: {error}"))?;
    if !output.status.success() {
        let detail = String::from_utf8_lossy(&output.stderr).trim().to_string();
        return Err(if detail.is_empty() {
            format!("DWG audit sidecar exited with status {}.", output.status)
        } else {
            format!(
                "DWG audit sidecar exited with status {}: {}",
                output.status, detail
            )
        });
    }
    let stdout = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(&stdout)
        .map_err(|error| format!("Failed to parse DWG audit sidecar JSON output: {error}"))
}

fn build_desktop_sidecar_command(
    app: &AppHandle,
    args: &[String],
) -> Result<std::process::Command, String> {
    let resource_dir = app.path().resource_dir().ok();
    build_sidecar_command(args, resource_dir)
}

fn default_workspace_root() -> Result<PathBuf, String> {
    let root = default_local_app_data_dir()?
        .join("dwg-audit")
        .join("sessions");
    fs::create_dir_all(&root).map_err(|error| {
        format!(
            "Failed to create workspace root {}: {error}",
            root.display()
        )
    })?;
    Ok(root)
}

fn default_state_db_path() -> Result<PathBuf, String> {
    let db_path = default_local_app_data_dir()?
        .join("dwg-audit")
        .join("desktop_state.db");
    if let Some(parent) = db_path.parent() {
        fs::create_dir_all(parent).map_err(|error| {
            format!(
                "Failed to create state DB directory {}: {error}",
                parent.display()
            )
        })?;
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
        .plugin(tauri_plugin_dialog::init())
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
