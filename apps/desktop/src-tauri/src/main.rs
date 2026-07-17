// Release builds must be a Windows GUI process. A CUI (console) desktop binary
// allocates a black terminal on launch; closing that console delivers
// CTRL_CLOSE_EVENT and tears down the entire app.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::env;
use std::fs;
use std::io::BufRead;
use std::io::BufReader;
use std::io::Read;
use std::path::PathBuf;
use std::process::Output;
use std::process::Stdio;
use std::sync::atomic::AtomicU32;
use std::sync::atomic::AtomicU64;
use std::sync::atomic::Ordering;
use std::sync::Mutex;
use std::thread::JoinHandle;
use std::time::Duration;
use std::time::Instant;

use serde_json::json;
use serde_json::Value;
use tauri::AppHandle;
use tauri::Emitter;
use tauri::Manager;

mod sidecar_runtime;

use sidecar_runtime::build_sidecar_command;

const DESKTOP_EVENT_NAME: &str = "dwg-audit://sidecar-event";
const PREVIEW_TIMEOUT: Duration = Duration::from_secs(15);
const PREVIEW_POLL_INTERVAL: Duration = Duration::from_millis(40);
static PREVIEW_GENERATION: AtomicU64 = AtomicU64::new(0);
static ACTIVE_PREVIEW_PID: AtomicU32 = AtomicU32::new(0);
static PREVIEW_GATE: Mutex<()> = Mutex::new(());

#[tauri::command]
async fn desktop_analyze_session(
    app: AppHandle,
    input_root: String,
    session_id: Option<String>,
) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        analyze_session_blocking(app, input_root, session_id)
    })
    .await
    .map_err(|error| format!("Analyze session task failed: {error}"))?
}

fn analyze_session_blocking(
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

    // Drain stderr off the critical path so a full stderr buffer cannot deadlock the sidecar.
    let stderr_thread = std::thread::spawn(move || {
        let mut text = String::new();
        let _ = BufReader::new(stderr).read_to_string(&mut text);
        text
    });

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
        // Best-effort emit: never abort a long audit because the UI dropped an event.
        let _ = app.emit(DESKTOP_EVENT_NAME, &payload);
    }

    let status = child
        .wait()
        .map_err(|error| format!("Failed to wait for DWG audit sidecar: {error}"))?;
    let stderr_text = stderr_thread
        .join()
        .unwrap_or_else(|_| String::from("Failed to join sidecar stderr thread."));

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
async fn desktop_list_recent_projects(app: AppHandle) -> Result<Value, String> {
    run_sidecar_json_async(
        app,
        vec![
            "list-recent-projects".to_string(),
            "--state-db".to_string(),
            default_state_db_path()?.to_string_lossy().to_string(),
        ],
    )
    .await
    .map(|payload| {
        payload
            .get("projects")
            .cloned()
            .unwrap_or(Value::Array(Vec::new()))
    })
}

#[tauri::command]
async fn desktop_load_result(app: AppHandle, project_id: String) -> Result<Value, String> {
    run_sidecar_json_async(
        app,
        vec![
            "load-result".to_string(),
            "--project-id".to_string(),
            project_id,
            "--state-db".to_string(),
            default_state_db_path()?.to_string_lossy().to_string(),
        ],
    )
    .await
}

#[tauri::command]
async fn desktop_render_preview(
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
    let generation = begin_preview_request();
    tauri::async_runtime::spawn_blocking(move || {
        run_preview_sidecar_json_owned(&app, args, generation)
    })
    .await
    .map_err(|error| format!("Preview sidecar task failed: {error}"))?
}

#[tauri::command]
fn desktop_cancel_preview() -> Value {
    cancel_preview_requests();
    json!({ "cancelled": true })
}

#[tauri::command]
async fn desktop_set_issue_status(
    app: AppHandle,
    project_id: String,
    issue_id: String,
    status: String,
) -> Result<Value, String> {
    run_sidecar_json_async(
        app,
        vec![
            "set-issue-status".to_string(),
            "--project-id".to_string(),
            project_id,
            "--issue-id".to_string(),
            issue_id,
            "--status".to_string(),
            status,
            "--state-db".to_string(),
            default_state_db_path()?.to_string_lossy().to_string(),
        ],
    )
    .await
}

#[tauri::command]
async fn desktop_delete_project(app: AppHandle, project_id: String) -> Result<Value, String> {
    let workspace_root = default_workspace_root()?;
    let state_db = default_state_db_path()?;
    run_sidecar_json_async(
        app,
        vec![
            "delete-project-record".to_string(),
            "--project-id".to_string(),
            project_id,
            "--workspace-root".to_string(),
            workspace_root.to_string_lossy().to_string(),
            "--state-db".to_string(),
            state_db.to_string_lossy().to_string(),
        ],
    )
    .await
}

#[tauri::command]
async fn desktop_cleanup_workspaces(app: AppHandle) -> Result<Value, String> {
    run_cleanup_workspaces_async(app).await
}

async fn run_cleanup_workspaces_async(app: AppHandle) -> Result<Value, String> {
    let workspace_root = default_workspace_root()?;
    let state_db = default_state_db_path()?;
    run_sidecar_json_async(
        app,
        vec![
            "cleanup-workspaces".to_string(),
            "--workspace-root".to_string(),
            workspace_root.to_string_lossy().to_string(),
            "--state-db".to_string(),
            state_db.to_string_lossy().to_string(),
        ],
    )
    .await
}

async fn run_sidecar_json_async(app: AppHandle, args: Vec<String>) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || run_sidecar_json_owned(&app, args))
        .await
        .map_err(|error| format!("Sidecar task failed: {error}"))?
}

fn run_sidecar_json_owned(app: &AppHandle, args: Vec<String>) -> Result<Value, String> {
    let output = build_desktop_sidecar_command(app, &args)?
        .output()
        .map_err(|error| format!("Failed to execute DWG audit sidecar: {error}"))?;
    parse_sidecar_json_output(output)
}

fn parse_sidecar_json_output(output: Output) -> Result<Value, String> {
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
    serde_json::from_str(stdout.trim())
        .map_err(|error| format!("Failed to parse DWG audit sidecar JSON output: {error}"))
}

fn begin_preview_request() -> u64 {
    PREVIEW_GENERATION.fetch_add(1, Ordering::SeqCst) + 1
}

fn is_current_preview_request(generation: u64) -> bool {
    PREVIEW_GENERATION.load(Ordering::SeqCst) == generation
}

fn cancel_preview_requests() {
    PREVIEW_GENERATION.fetch_add(1, Ordering::SeqCst);
    let pid = ACTIVE_PREVIEW_PID.load(Ordering::SeqCst);
    if pid != 0 {
        terminate_process_tree_by_pid(pid);
    }
}

fn run_preview_sidecar_json_owned(
    app: &AppHandle,
    args: Vec<String>,
    generation: u64,
) -> Result<Value, String> {
    let _gate = PREVIEW_GATE
        .lock()
        .map_err(|_| "Preview sidecar gate is unavailable.".to_string())?;
    if !is_current_preview_request(generation) {
        return Err("Preview request superseded.".to_string());
    }

    let mut child = build_desktop_sidecar_command(app, &args)?
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| format!("Failed to execute DWG audit preview sidecar: {error}"))?;
    let _active_process = ActivePreviewProcess::new(child.id());
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "DWG audit preview sidecar stdout pipe is unavailable.".to_string())?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| "DWG audit preview sidecar stderr pipe is unavailable.".to_string())?;
    let stdout_thread = drain_preview_pipe(stdout, "stdout");
    let stderr_thread = drain_preview_pipe(stderr, "stderr");
    let started = Instant::now();

    loop {
        if !is_current_preview_request(generation) {
            terminate_preview_child(&mut child);
            discard_preview_output(stdout_thread, stderr_thread);
            return Err("Preview request superseded.".to_string());
        }
        if started.elapsed() >= PREVIEW_TIMEOUT {
            terminate_preview_child(&mut child);
            discard_preview_output(stdout_thread, stderr_thread);
            return Err(format!(
                "Preview generation timed out after {} seconds.",
                PREVIEW_TIMEOUT.as_secs()
            ));
        }
        match child
            .try_wait()
            .map_err(|error| format!("Failed to poll DWG audit preview sidecar: {error}"))?
        {
            Some(status) => {
                let stdout = join_preview_pipe(stdout_thread)?;
                let stderr = join_preview_pipe(stderr_thread)?;
                let output = Output {
                    status,
                    stdout,
                    stderr,
                };
                return parse_sidecar_json_output(output);
            }
            None => std::thread::sleep(PREVIEW_POLL_INTERVAL),
        }
    }
}

fn drain_preview_pipe<R>(mut pipe: R, label: &'static str) -> JoinHandle<Result<Vec<u8>, String>>
where
    R: Read + Send + 'static,
{
    std::thread::spawn(move || {
        let mut bytes = Vec::new();
        pipe.read_to_end(&mut bytes)
            .map_err(|error| format!("Failed to read preview sidecar {label}: {error}"))?;
        Ok(bytes)
    })
}

fn join_preview_pipe(thread: JoinHandle<Result<Vec<u8>, String>>) -> Result<Vec<u8>, String> {
    thread
        .join()
        .map_err(|_| "Preview sidecar output reader panicked.".to_string())?
}

fn discard_preview_output(
    stdout_thread: JoinHandle<Result<Vec<u8>, String>>,
    stderr_thread: JoinHandle<Result<Vec<u8>, String>>,
) {
    let _ = stdout_thread.join();
    let _ = stderr_thread.join();
}

struct ActivePreviewProcess {
    pid: u32,
}

impl ActivePreviewProcess {
    fn new(pid: u32) -> Self {
        ACTIVE_PREVIEW_PID.store(pid, Ordering::SeqCst);
        Self { pid }
    }
}

impl Drop for ActivePreviewProcess {
    fn drop(&mut self) {
        let _ =
            ACTIVE_PREVIEW_PID.compare_exchange(self.pid, 0, Ordering::SeqCst, Ordering::SeqCst);
    }
}

fn terminate_preview_child(child: &mut std::process::Child) {
    terminate_process_tree_by_pid(child.id());
    let _ = child.kill();
    let _ = child.wait();
}

#[cfg(windows)]
fn terminate_process_tree_by_pid(pid: u32) {
    use std::os::windows::process::CommandExt;

    const CREATE_NO_WINDOW: u32 = 0x08000000;
    let _ = std::process::Command::new("taskkill")
        .args(["/PID", &pid.to_string(), "/T", "/F"])
        .creation_flags(CREATE_NO_WINDOW)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status();
}

#[cfg(not(windows))]
fn terminate_process_tree_by_pid(_pid: u32) {}

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
            desktop_cancel_preview,
            desktop_set_issue_status,
            desktop_delete_project,
            desktop_cleanup_workspaces
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|_app_handle, event| {
            if matches!(
                event,
                tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit
            ) {
                cancel_preview_requests();
            }
        });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn newer_preview_request_supersedes_older_generation() {
        let older = begin_preview_request();
        assert!(is_current_preview_request(older));

        let newer = begin_preview_request();
        assert!(!is_current_preview_request(older));
        assert!(is_current_preview_request(newer));
    }

    #[test]
    fn preview_pipe_drain_handles_payload_larger_than_windows_pipe_buffer() {
        let payload = vec![b'x'; 256 * 1024];
        let reader = std::io::Cursor::new(payload.clone());

        let drained = join_preview_pipe(drain_preview_pipe(reader, "test")).unwrap();

        assert_eq!(drained, payload);
    }
}
