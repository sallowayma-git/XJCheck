// Release builds must be a Windows GUI process. A CUI (console) desktop binary
// allocates a black terminal on launch; closing that console delivers
// CTRL_CLOSE_EVENT and tears down the entire app.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::collections::HashMap;
use std::env;
use std::fs;
use std::io::BufRead;
use std::io::BufReader;
use std::io::Read;
use std::path::PathBuf;
use std::process::Output;
use std::process::Stdio;
use std::sync::atomic::AtomicBool;
use std::sync::atomic::AtomicU64;
use std::sync::atomic::Ordering;
use std::sync::mpsc;
use std::sync::Mutex;
use std::time::Duration;
use std::time::Instant;
use std::time::SystemTime;
use std::time::UNIX_EPOCH;

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
const PREVIEW_PIPE_DRAIN_TIMEOUT: Duration = Duration::from_secs(1);
const LEGACY_PREVIEW_CLIENT_SESSION_ID: &str = "legacy";
static PREVIEW_STATE: Mutex<PreviewState> = Mutex::new(PreviewState {
    next_generation: 0,
    next_client_epoch: 0,
    known_client_sessions: Vec::new(),
    current_client_session_id: None,
    current_client_session_epoch: None,
    latest_client_request: None,
    active: None,
});
static PREVIEW_GATE: Mutex<()> = Mutex::new(());
static SHUTTING_DOWN: AtomicBool = AtomicBool::new(false);
static ACTIVE_SIDECAR_PIDS: Mutex<Vec<u32>> = Mutex::new(Vec::new());
static PROTECTED_CLEANUP_PIDS: Mutex<Vec<u32>> = Mutex::new(Vec::new());
static DESKTOP_RESOURCE_DIR: Mutex<Option<PathBuf>> = Mutex::new(None);
static SESSION_SEQUENCE: AtomicU64 = AtomicU64::new(0);

#[tauri::command]
async fn desktop_analyze_session(
    app: AppHandle,
    input_root: String,
    session_id: Option<String>,
) -> Result<Value, String> {
    let session_id = session_id.unwrap_or_else(new_session_id);
    tauri::async_runtime::spawn_blocking(move || {
        analyze_session_blocking(app, input_root, session_id)
    })
    .await
    .map_err(|error| format!("Analyze session task failed: {error}"))?
}

fn analyze_session_blocking(
    app: AppHandle,
    input_root: String,
    session_id: String,
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
        "--session-id".to_string(),
        session_id.clone(),
        "--defer-cleanup".to_string(),
    ];
    // Only append `--config` when the user has actually written an override.
    // Absence reproduces the pre-settings spawn exactly (DEFAULT_CONFIG only).
    if let Some(path) = settings_override_path() {
        args.push("--config".to_string());
        args.push(path.to_string_lossy().to_string());
    }

    let mut child = build_desktop_sidecar_command(&app, &args)?
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| format!("Failed to start DWG audit sidecar: {error}"))?;
    let _active_process = ActiveSidecarProcess::new(child.id());

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

    if let Err(error) = spawn_session_cleanup(&session_id, &workspace_root, &state_db) {
        let _ = app.emit(
            DESKTOP_EVENT_NAME,
            &json!({
                "event": "warning",
                "stage": "cleanup",
                "session_id": session_id,
                "message": error,
            }),
        );
    }

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
    let workspace_root = default_workspace_root()?;
    run_sidecar_json_async(
        app,
        vec![
            "list-recent-projects".to_string(),
            "--state-db".to_string(),
            default_state_db_path()?.to_string_lossy().to_string(),
            "--workspace-root".to_string(),
            workspace_root.to_string_lossy().to_string(),
            "--older-than-seconds".to_string(),
            "3600".to_string(),
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
async fn desktop_load_result_summary(app: AppHandle, project_id: String) -> Result<Value, String> {
    run_sidecar_json_async(
        app,
        vec![
            "load-result-summary".to_string(),
            "--project-id".to_string(),
            project_id,
            "--state-db".to_string(),
            default_state_db_path()?.to_string_lossy().to_string(),
        ],
    )
    .await
}

#[tauri::command]
async fn desktop_load_result_issues(
    app: AppHandle,
    project_id: String,
    limit: Option<u64>,
    offset: Option<u64>,
) -> Result<Value, String> {
    run_sidecar_json_async(
        app,
        vec![
            "load-result-issues".to_string(),
            "--project-id".to_string(),
            project_id,
            "--state-db".to_string(),
            default_state_db_path()?.to_string_lossy().to_string(),
            "--limit".to_string(),
            limit.unwrap_or(200).to_string(),
            "--offset".to_string(),
            offset.unwrap_or(0).to_string(),
        ],
    )
    .await
}

#[tauri::command]
async fn desktop_load_result_issue_detail(
    app: AppHandle,
    project_id: String,
    issue_id: String,
) -> Result<Value, String> {
    run_sidecar_json_async(
        app,
        vec![
            "load-result-issue-detail".to_string(),
            "--project-id".to_string(),
            project_id,
            "--issue-id".to_string(),
            issue_id,
            "--state-db".to_string(),
            default_state_db_path()?.to_string_lossy().to_string(),
        ],
    )
    .await
}

#[tauri::command]
fn desktop_register_preview_session(client_session_id: String) -> Result<Value, String> {
    let client_session_id = client_session_id.trim().to_string();
    if client_session_id.is_empty() || client_session_id == LEGACY_PREVIEW_CLIENT_SESSION_ID {
        return Err("A non-empty modern preview session id is required.".to_string());
    }
    let client_session_epoch = register_preview_client_session(client_session_id.clone())?;
    Ok(json!({
        "client_session_id": client_session_id,
        "client_session_epoch": client_session_epoch,
    }))
}

#[tauri::command]
async fn desktop_render_preview(
    app: AppHandle,
    request_id: String,
    request_generation: u64,
    client_session_id: Option<String>,
    client_session_epoch: Option<u64>,
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
    let token = begin_preview_request(
        normalize_preview_client_session_id(client_session_id),
        client_session_epoch,
        request_id,
        request_generation,
    )
    .ok_or_else(|| "Preview request superseded.".to_string())?;
    tauri::async_runtime::spawn_blocking(move || run_preview_sidecar_json_owned(&app, args, token))
        .await
        .map_err(|error| format!("Preview sidecar task failed: {error}"))?
}

#[tauri::command]
fn desktop_cancel_preview(
    request_id: String,
    request_generation: u64,
    client_session_id: Option<String>,
    client_session_epoch: Option<u64>,
) -> Value {
    let cancelled = cancel_preview_request(
        &normalize_preview_client_session_id(client_session_id),
        client_session_epoch,
        &request_id,
        request_generation,
    );
    json!({
        "cancelled": cancelled,
        "request_id": request_id,
        "request_generation": request_generation,
    })
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
    let child = build_desktop_sidecar_command(app, &args)?
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| format!("Failed to execute DWG audit sidecar: {error}"))?;
    let _active_process = ActiveSidecarProcess::new(child.id());
    let output = child
        .wait_with_output()
        .map_err(|error| format!("Failed to wait for DWG audit sidecar: {error}"))?;
    parse_sidecar_json_output(output)
}

fn spawn_session_cleanup(
    session_id: &str,
    workspace_root: &std::path::Path,
    state_db: &std::path::Path,
) -> Result<u32, String> {
    spawn_cleanup_sidecar(vec![
        "compact-session-workspace".to_string(),
        "--session-id".to_string(),
        session_id.to_string(),
        "--workspace-root".to_string(),
        workspace_root.to_string_lossy().to_string(),
        "--state-db".to_string(),
        state_db.to_string_lossy().to_string(),
    ])
}

fn spawn_global_cleanup() -> Result<u32, String> {
    spawn_cleanup_sidecar(vec![
        "cleanup-workspaces".to_string(),
        "--workspace-root".to_string(),
        default_workspace_root()?.to_string_lossy().to_string(),
        "--state-db".to_string(),
        default_state_db_path()?.to_string_lossy().to_string(),
    ])
}

fn spawn_cleanup_sidecar(args: Vec<String>) -> Result<u32, String> {
    let resource_dir = DESKTOP_RESOURCE_DIR
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
        .clone();
    let mut command = build_sidecar_command(&args, resource_dir)?;
    command
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;

        const BELOW_NORMAL_PRIORITY_CLASS: u32 = 0x0000_4000;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        command.creation_flags(CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS);
    }

    let mut child = command
        .spawn()
        .map_err(|error| format!("Failed to start cleanup sidecar: {error}"))?;
    let pid = child.id();
    PROTECTED_CLEANUP_PIDS
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
        .push(pid);
    std::thread::spawn(move || {
        let _ = child.wait();
        PROTECTED_CLEANUP_PIDS
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .retain(|active_pid| *active_pid != pid);
    });
    Ok(pid)
}

fn new_session_id() -> String {
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis();
    let sequence = SESSION_SEQUENCE.fetch_add(1, Ordering::SeqCst) + 1;
    format!(
        "desktop-{timestamp:x}-{:x}-{sequence:x}",
        std::process::id()
    )
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

fn attach_preview_request_id(mut payload: Value, request_id: &str) -> Result<Value, String> {
    let object = payload
        .as_object_mut()
        .ok_or_else(|| "Preview sidecar response must be a JSON object.".to_string())?;
    object.insert(
        "request_id".to_string(),
        Value::String(request_id.to_string()),
    );
    Ok(payload)
}

fn normalize_preview_client_session_id(value: Option<String>) -> String {
    value
        .map(|session_id| session_id.trim().to_string())
        .filter(|session_id| !session_id.is_empty())
        .unwrap_or_else(|| LEGACY_PREVIEW_CLIENT_SESSION_ID.to_string())
}

fn register_preview_client_session(client_session_id: String) -> Result<u64, String> {
    PREVIEW_STATE
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
        .register_client_session(client_session_id)
}

fn begin_preview_request(
    client_session_id: String,
    client_session_epoch: Option<u64>,
    request_id: String,
    client_generation: u64,
) -> Option<PreviewToken> {
    PREVIEW_STATE
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
        .begin(
            client_session_id,
            client_session_epoch,
            request_id,
            client_generation,
        )
}

fn is_current_preview_request(token: &PreviewToken) -> bool {
    PREVIEW_STATE
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
        .is_current(token)
}

fn cancel_preview_request(
    client_session_id: &str,
    client_session_epoch: Option<u64>,
    request_id: &str,
    client_generation: u64,
) -> bool {
    PREVIEW_STATE
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
        .cancel(
            client_session_id,
            client_session_epoch,
            request_id,
            client_generation,
        )
}

fn register_preview_pid(token: &PreviewToken, pid: u32) -> bool {
    PREVIEW_STATE
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
        .register_pid(token, pid)
}

fn release_preview_request(token: &PreviewToken, pid: Option<u32>) -> bool {
    PREVIEW_STATE
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
        .release(token, pid)
}

fn run_preview_sidecar_json_owned(
    app: &AppHandle,
    args: Vec<String>,
    token: PreviewToken,
) -> Result<Value, String> {
    let _gate = PREVIEW_GATE
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner());
    if !is_current_preview_request(&token) {
        return Err("Preview request superseded.".to_string());
    }
    let mut active_request = ActivePreviewRequest::new(token.clone());

    let mut command = build_desktop_sidecar_command(app, &args)?;
    if !is_current_preview_request(&token) {
        return Err("Preview request superseded.".to_string());
    }
    let mut child = command
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| format!("Failed to execute DWG audit preview sidecar: {error}"))?;
    let _active_sidecar = ActiveSidecarProcess::new(child.id());
    if !active_request.register_pid(child.id()) {
        terminate_preview_child(&mut child);
        return Err("Preview request superseded.".to_string());
    }
    let stdout = match child.stdout.take() {
        Some(stdout) => stdout,
        None => {
            terminate_preview_child(&mut child);
            return Err("DWG audit preview sidecar stdout pipe is unavailable.".to_string());
        }
    };
    let stderr = match child.stderr.take() {
        Some(stderr) => stderr,
        None => {
            terminate_preview_child(&mut child);
            return Err("DWG audit preview sidecar stderr pipe is unavailable.".to_string());
        }
    };
    let stdout_drain = match drain_preview_pipe(stdout, "stdout") {
        Ok(drain) => drain,
        Err(error) => {
            terminate_preview_child(&mut child);
            return Err(error);
        }
    };
    let stderr_drain = match drain_preview_pipe(stderr, "stderr") {
        Ok(drain) => drain,
        Err(error) => {
            terminate_preview_child(&mut child);
            drop(stdout_drain);
            return Err(error);
        }
    };
    let started = Instant::now();

    loop {
        if !is_current_preview_request(&token) {
            terminate_preview_child(&mut child);
            discard_preview_output(stdout_drain, stderr_drain);
            return Err("Preview request superseded.".to_string());
        }
        if started.elapsed() >= PREVIEW_TIMEOUT {
            terminate_preview_child(&mut child);
            discard_preview_output(stdout_drain, stderr_drain);
            return Err(format!(
                "Preview generation timed out after {} seconds.",
                PREVIEW_TIMEOUT.as_secs()
            ));
        }
        let child_status = match child.try_wait() {
            Ok(status) => status,
            Err(error) => {
                terminate_preview_child(&mut child);
                discard_preview_output(stdout_drain, stderr_drain);
                return Err(format!("Failed to poll DWG audit preview sidecar: {error}"));
            }
        };
        match child_status {
            Some(status) => {
                let stdout = join_preview_pipe(stdout_drain)?;
                let stderr = join_preview_pipe(stderr_drain)?;
                let output = Output {
                    status,
                    stdout,
                    stderr,
                };
                let payload = attach_preview_request_id(
                    parse_sidecar_json_output(output)?,
                    &token.request_id,
                )?;
                if !active_request.finish() {
                    return Err("Preview request superseded.".to_string());
                }
                return Ok(payload);
            }
            None => std::thread::sleep(PREVIEW_POLL_INTERVAL),
        }
    }
}

struct PreviewPipeDrain {
    label: &'static str,
    receiver: mpsc::Receiver<Result<Vec<u8>, String>>,
}

fn drain_preview_pipe<R>(mut pipe: R, label: &'static str) -> Result<PreviewPipeDrain, String>
where
    R: Read + Send + 'static,
{
    let (sender, receiver) = mpsc::sync_channel(1);
    std::thread::Builder::new()
        .name(format!("preview-{label}-reader"))
        .spawn(move || {
            let result = (|| {
                let mut bytes = Vec::new();
                pipe.read_to_end(&mut bytes)
                    .map_err(|error| format!("Failed to read preview sidecar {label}: {error}"))?;
                Ok(bytes)
            })();
            let _ = sender.send(result);
        })
        .map_err(|error| format!("Failed to start preview sidecar {label} reader: {error}"))?;
    Ok(PreviewPipeDrain { label, receiver })
}

fn join_preview_pipe(drain: PreviewPipeDrain) -> Result<Vec<u8>, String> {
    join_preview_pipe_with_timeout(drain, PREVIEW_PIPE_DRAIN_TIMEOUT)
}

fn join_preview_pipe_with_timeout(
    drain: PreviewPipeDrain,
    timeout: Duration,
) -> Result<Vec<u8>, String> {
    match drain.receiver.recv_timeout(timeout) {
        Ok(result) => result,
        Err(mpsc::RecvTimeoutError::Timeout) => Err(format!(
            "Timed out waiting for preview sidecar {} pipe to close.",
            drain.label
        )),
        Err(mpsc::RecvTimeoutError::Disconnected) => Err(format!(
            "Preview sidecar {} output reader stopped unexpectedly.",
            drain.label
        )),
    }
}

fn discard_preview_output(stdout_drain: PreviewPipeDrain, stderr_drain: PreviewPipeDrain) {
    drop(stdout_drain);
    drop(stderr_drain);
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct PreviewToken {
    client_session_id: String,
    client_epoch: u64,
    request_id: String,
    client_generation: u64,
    generation: u64,
}

#[derive(Debug)]
struct PreviewOwner {
    token: PreviewToken,
    pid: Option<u32>,
}

#[derive(Debug)]
struct PreviewClientRequest {
    client_session_id: String,
    client_epoch: u64,
    request_id: String,
    generation: u64,
    cancelled: bool,
}

#[derive(Debug)]
struct PreviewState {
    next_generation: u64,
    next_client_epoch: u64,
    known_client_sessions: Vec<(String, u64)>,
    current_client_session_id: Option<String>,
    current_client_session_epoch: Option<u64>,
    latest_client_request: Option<PreviewClientRequest>,
    active: Option<PreviewOwner>,
}

impl PreviewState {
    fn register_client_session(&mut self, client_session_id: String) -> Result<u64, String> {
        if client_session_id == LEGACY_PREVIEW_CLIENT_SESSION_ID {
            return Err("The reserved legacy preview session cannot be registered.".to_string());
        }
        if let Some((_, epoch)) = self
            .known_client_sessions
            .iter()
            .find(|(session_id, _)| session_id == &client_session_id)
        {
            return Ok(*epoch);
        }

        self.next_client_epoch = self.next_client_epoch.checked_add(1).unwrap_or(1);
        let client_epoch = self.next_client_epoch;
        self.known_client_sessions
            .push((client_session_id.clone(), client_epoch));
        self.current_client_session_id = Some(client_session_id);
        self.current_client_session_epoch = Some(client_epoch);
        self.latest_client_request = None;
        self.active = None;
        Ok(client_epoch)
    }

    fn accepts_request(&mut self, client_session_id: &str, client_epoch: Option<u64>) -> bool {
        if client_session_id == LEGACY_PREVIEW_CLIENT_SESSION_ID && client_epoch.is_none() {
            if self.current_client_session_id.is_none() {
                self.known_client_sessions
                    .push((client_session_id.to_string(), 0));
                self.current_client_session_id = Some(client_session_id.to_string());
                self.current_client_session_epoch = Some(0);
            }
            return self.current_client_session_id.as_deref() == Some(client_session_id)
                && self.current_client_session_epoch == Some(0);
        }

        let Some(client_epoch) = client_epoch else {
            return false;
        };
        self.current_client_session_id.as_deref() == Some(client_session_id)
            && self.current_client_session_epoch == Some(client_epoch)
            && self
                .known_client_sessions
                .iter()
                .any(|(session_id, epoch)| {
                    session_id == client_session_id && *epoch == client_epoch
                })
    }

    fn begin(
        &mut self,
        client_session_id: String,
        client_epoch: Option<u64>,
        request_id: String,
        client_generation: u64,
    ) -> Option<PreviewToken> {
        if !self.accepts_request(&client_session_id, client_epoch) {
            return None;
        }
        let client_epoch = self.current_client_session_epoch?;
        if self
            .latest_client_request
            .as_ref()
            .is_some_and(|latest| client_generation <= latest.generation)
        {
            return None;
        }
        self.next_generation = self.next_generation.checked_add(1).unwrap_or(1);
        let token = PreviewToken {
            client_session_id: client_session_id.clone(),
            client_epoch,
            request_id: request_id.clone(),
            client_generation,
            generation: self.next_generation,
        };
        self.latest_client_request = Some(PreviewClientRequest {
            client_session_id,
            client_epoch,
            request_id,
            generation: client_generation,
            cancelled: false,
        });
        self.active = Some(PreviewOwner {
            token: token.clone(),
            pid: None,
        });
        Some(token)
    }

    fn is_current(&self, token: &PreviewToken) -> bool {
        self.active
            .as_ref()
            .is_some_and(|owner| owner.token == *token)
    }

    fn register_pid(&mut self, token: &PreviewToken, pid: u32) -> bool {
        let Some(owner) = self
            .active
            .as_mut()
            .filter(|owner| owner.token == *token && owner.pid.is_none())
        else {
            return false;
        };
        owner.pid = Some(pid);
        true
    }

    fn cancel(
        &mut self,
        client_session_id: &str,
        client_epoch: Option<u64>,
        request_id: &str,
        client_generation: u64,
    ) -> bool {
        if !self.accepts_request(client_session_id, client_epoch) {
            return false;
        }
        let client_epoch = self.current_client_session_epoch.unwrap_or(0);
        match self.latest_client_request.as_mut() {
            Some(latest) if client_generation < latest.generation => false,
            Some(latest) if client_generation == latest.generation => {
                if latest.client_session_id != client_session_id
                    || latest.client_epoch != client_epoch
                    || latest.request_id != request_id
                    || latest.cancelled
                {
                    return false;
                }
                latest.cancelled = true;
                if self.active.as_ref().is_some_and(|owner| {
                    owner.token.client_session_id == client_session_id
                        && owner.token.client_epoch == client_epoch
                        && owner.token.request_id == request_id
                        && owner.token.client_generation == client_generation
                }) {
                    self.active = None;
                }
                true
            }
            _ => {
                self.latest_client_request = Some(PreviewClientRequest {
                    client_session_id: client_session_id.to_string(),
                    client_epoch,
                    request_id: request_id.to_string(),
                    generation: client_generation,
                    cancelled: true,
                });
                if self.active.as_ref().is_some_and(|owner| {
                    owner.token.client_session_id == client_session_id
                        && owner.token.client_epoch == client_epoch
                        && owner.token.client_generation < client_generation
                }) {
                    self.active = None;
                }
                true
            }
        }
    }

    fn release(&mut self, token: &PreviewToken, pid: Option<u32>) -> bool {
        if !self
            .active
            .as_ref()
            .is_some_and(|owner| owner.token == *token && owner.pid == pid)
        {
            return false;
        }
        self.active = None;
        true
    }
}

struct ActivePreviewRequest {
    token: PreviewToken,
    pid: Option<u32>,
    released: bool,
}

struct ActiveSidecarProcess {
    pid: u32,
}

impl ActiveSidecarProcess {
    fn new(pid: u32) -> Self {
        let terminate_now = {
            let mut active = ACTIVE_SIDECAR_PIDS
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner());
            if SHUTTING_DOWN.load(Ordering::SeqCst) {
                true
            } else {
                if !active.contains(&pid) {
                    active.push(pid);
                }
                false
            }
        };
        if terminate_now {
            terminate_process_tree_by_pid(pid);
        }
        Self { pid }
    }
}

impl Drop for ActiveSidecarProcess {
    fn drop(&mut self) {
        ACTIVE_SIDECAR_PIDS
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .retain(|pid| *pid != self.pid);
    }
}

fn terminate_all_active_sidecars() {
    SHUTTING_DOWN.store(true, Ordering::SeqCst);
    let active = {
        let mut pids = ACTIVE_SIDECAR_PIDS
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        pids.drain(..).collect::<Vec<_>>()
    };
    for pid in active {
        terminate_process_tree_by_pid(pid);
    }
}

fn force_shutdown() -> ! {
    if SHUTTING_DOWN.swap(true, Ordering::SeqCst) {
        std::process::exit(0);
    }
    let _ = spawn_global_cleanup();
    terminate_descendant_processes();
    std::process::exit(0);
}

#[cfg(windows)]
fn terminate_descendant_processes() {
    use windows_sys::Win32::Foundation::CloseHandle;
    use windows_sys::Win32::Foundation::INVALID_HANDLE_VALUE;
    use windows_sys::Win32::System::Diagnostics::ToolHelp::CreateToolhelp32Snapshot;
    use windows_sys::Win32::System::Diagnostics::ToolHelp::Process32FirstW;
    use windows_sys::Win32::System::Diagnostics::ToolHelp::Process32NextW;
    use windows_sys::Win32::System::Diagnostics::ToolHelp::PROCESSENTRY32W;
    use windows_sys::Win32::System::Diagnostics::ToolHelp::TH32CS_SNAPPROCESS;
    use windows_sys::Win32::System::Threading::OpenProcess;
    use windows_sys::Win32::System::Threading::TerminateProcess;
    use windows_sys::Win32::System::Threading::PROCESS_TERMINATE;

    unsafe {
        let snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
        if snapshot == INVALID_HANDLE_VALUE {
            return;
        }

        let current_pid = std::process::id();
        let mut entry: PROCESSENTRY32W = std::mem::zeroed();
        entry.dwSize = std::mem::size_of::<PROCESSENTRY32W>() as u32;
        let mut parents = HashMap::new();
        if Process32FirstW(snapshot, &mut entry) != 0 {
            loop {
                parents.insert(entry.th32ProcessID, entry.th32ParentProcessID);
                if Process32NextW(snapshot, &mut entry) == 0 {
                    break;
                }
            }
        }
        let _ = CloseHandle(snapshot);

        let protected = PROTECTED_CLEANUP_PIDS
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .clone();
        let descendants = descendant_processes_to_terminate(&parents, current_pid, &protected);

        for (pid, _) in descendants {
            let process = OpenProcess(PROCESS_TERMINATE, 0, pid);
            if !process.is_null() {
                let _ = TerminateProcess(process, 0);
                let _ = CloseHandle(process);
            }
        }
    }
}

#[cfg(not(windows))]
fn terminate_descendant_processes() {}

fn descendant_processes_to_terminate(
    parents: &HashMap<u32, u32>,
    current_pid: u32,
    protected_roots: &[u32],
) -> Vec<(u32, usize)> {
    let mut descendants = parents
        .keys()
        .filter_map(|pid| {
            if protected_roots.contains(pid) {
                return None;
            }
            let mut ancestor = *pid;
            let mut depth = 0usize;
            while let Some(parent) = parents.get(&ancestor) {
                depth += 1;
                if protected_roots.contains(parent) {
                    return None;
                }
                if *parent == current_pid {
                    return Some((*pid, depth));
                }
                if *parent == 0 || *parent == ancestor || depth > parents.len() {
                    break;
                }
                ancestor = *parent;
            }
            None
        })
        .collect::<Vec<_>>();
    descendants.sort_unstable_by(|left, right| right.1.cmp(&left.1));
    descendants
}

impl ActivePreviewRequest {
    fn new(token: PreviewToken) -> Self {
        Self {
            token,
            pid: None,
            released: false,
        }
    }

    fn register_pid(&mut self, pid: u32) -> bool {
        if !register_preview_pid(&self.token, pid) {
            return false;
        }
        self.pid = Some(pid);
        true
    }

    fn finish(&mut self) -> bool {
        let released = release_preview_request(&self.token, self.pid);
        self.released = true;
        released
    }
}

impl Drop for ActivePreviewRequest {
    fn drop(&mut self) {
        if !self.released {
            let _ = release_preview_request(&self.token, self.pid);
        }
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

/// Persisted settings override path. The file is written as JSON (which YAML 1.2
/// accepts), so the Python side can read it via `yaml.safe_load` and deep-merge
/// against `DEFAULT_CONFIG` without adding a YAML serializer dependency to the
/// desktop crate.
fn default_settings_path() -> Result<PathBuf, String> {
    let path = default_local_app_data_dir()?
        .join("dwg-audit")
        .join("desktop_settings.yml");
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|error| {
            format!(
                "Failed to create settings directory {}: {error}",
                parent.display()
            )
        })?;
    }
    Ok(path)
}

/// Return the settings override path only when the file actually exists with
/// content. This keeps the analyze sidecar spawn identical to the pre-settings
/// flow (no `--config`) when no override has ever been written.
fn settings_override_path() -> Option<PathBuf> {
    let path = default_settings_path().ok()?;
    match fs::metadata(&path) {
        Ok(meta) if meta.len() > 0 => Some(path),
        _ => None,
    }
}

#[tauri::command]
async fn desktop_read_settings(_app: AppHandle) -> Result<Value, String> {
    let path = default_settings_path()?;
    if !path.exists() {
        return Ok(json!({}));
    }
    let raw = fs::read_to_string(&path)
        .map_err(|error| format!("Failed to read settings {}: {error}", path.display()))?;
    serde_json::from_str::<Value>(&raw)
        .map_err(|error| format!("Failed to parse settings {}: {error}", path.display()))
}

#[tauri::command]
async fn desktop_write_settings(_app: AppHandle, settings: Value) -> Result<Value, String> {
    // The frontend always sends the full normalized object; validate the shape
    // we actually persist so a stray client cannot write arbitrary YAML into the
    // directory.
    let payload = normalize_settings_payload(&settings)?;
    let path = default_settings_path()?;
    if is_default_settings_payload(&payload) {
        // Removing the file restores the exact pre-settings spawn shape; the
        // analyze sidecar will receive no `--config` arg.
        let _ = fs::remove_file(&path);
        return Ok(json!({}));
    }
    fs::write(
        &path,
        serde_json::to_string_pretty(&payload).unwrap_or_else(|_| Value::Null.to_string()),
    )
    .map_err(|error| format!("Failed to write settings {}: {error}", path.display()))?;
    Ok(payload)
}

fn normalize_settings_payload(input: &Value) -> Result<Value, String> {
    let convert_workers = pick_u64(input, "convertWorkers", 0);
    let oda_timeout_seconds = pick_u64(input, "odaTimeoutSeconds", 300);
    let cache_cap_bytes = match input.get("cacheCapBytes") {
        Some(Value::Null) => None,
        Some(value) => {
            Some(as_u64(value).ok_or("cacheCapBytes must be a non-negative integer or null")?)
        }
        None => None,
    };
    let stage_telemetry_enabled = match input.get("stageTelemetryEnabled") {
        Some(Value::Bool(value)) => *value,
        Some(_) => return Err("stageTelemetryEnabled must be a boolean".to_string()),
        None => false,
    };
    if oda_timeout_seconds < 1 || oda_timeout_seconds > 86400 {
        return Err("oda_timeout_seconds must be between 1 and 86400".to_string());
    }
    if convert_workers > 16 {
        return Err("convert_workers must be between 0 and 16".to_string());
    }
    // Translate the flat frontend shape into the YAML fragment the Python side
    // already deep-merges against DEFAULT_CONFIG.
    let mut payload = json!({
        "ingest": {
            "convert_workers": convert_workers,
            "oda_timeout_seconds": oda_timeout_seconds,
        },
        "runtime": {
            "stage_telemetry": stage_telemetry_enabled,
        },
    });
    if let Some(cap) = cache_cap_bytes {
        payload["runtime"]["cache_cap_bytes"] = json!(cap);
    }
    Ok(payload)
}

fn pick_u64(input: &Value, key: &str, default: u64) -> u64 {
    match input.get(key) {
        Some(value) => as_u64(value).unwrap_or(default),
        None => default,
    }
}

fn as_u64(value: &Value) -> Option<u64> {
    if let Some(number) = value.as_u64() {
        return Some(number);
    }
    if let Some(number) = value.as_i64() {
        return Some(u64::try_from(number.max(0)).unwrap_or(0));
    }
    if let Some(number) = value.as_f64() {
        if number.is_finite() && number >= 0.0 {
            return Some(number as u64);
        }
    }
    None
}

fn is_default_settings_payload(payload: &Value) -> bool {
    let convert_workers = payload
        .get("ingest")
        .and_then(|v| v.get("convert_workers"))
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let oda_timeout_seconds = payload
        .get("ingest")
        .and_then(|v| v.get("oda_timeout_seconds"))
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let stage_telemetry = payload
        .get("runtime")
        .and_then(|v| v.get("stage_telemetry"))
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let cache_cap = payload
        .get("runtime")
        .and_then(|v| v.get("cache_cap_bytes"));
    convert_workers == 0 && oda_timeout_seconds == 300 && !stage_telemetry && cache_cap.is_none()
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
        .setup(|app| {
            *DESKTOP_RESOURCE_DIR
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner()) = app.path().resource_dir().ok();
            Ok(())
        })
        .on_window_event(|_window, event| {
            if matches!(event, tauri::WindowEvent::CloseRequested { .. }) {
                force_shutdown();
            }
        })
        .invoke_handler(tauri::generate_handler![
            desktop_analyze_session,
            desktop_list_recent_projects,
            desktop_load_result,
            desktop_load_result_summary,
            desktop_load_result_issues,
            desktop_load_result_issue_detail,
            desktop_register_preview_session,
            desktop_render_preview,
            desktop_cancel_preview,
            desktop_set_issue_status,
            desktop_delete_project,
            desktop_cleanup_workspaces,
            desktop_read_settings,
            desktop_write_settings
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|_app_handle, event| match event {
            tauri::RunEvent::ExitRequested { .. } => force_shutdown(),
            tauri::RunEvent::Exit => terminate_all_active_sidecars(),
            _ => {}
        });
}

#[cfg(test)]
mod tests {
    use super::*;

    struct BlockingReader {
        release: mpsc::Receiver<()>,
    }

    impl Read for BlockingReader {
        fn read(&mut self, _buffer: &mut [u8]) -> std::io::Result<usize> {
            let _ = self.release.recv();
            Ok(0)
        }
    }

    fn preview_state() -> PreviewState {
        PreviewState {
            next_generation: 0,
            next_client_epoch: 0,
            known_client_sessions: Vec::new(),
            current_client_session_id: None,
            current_client_session_epoch: None,
            latest_client_request: None,
            active: None,
        }
    }

    fn register(state: &mut PreviewState, session: &str) -> u64 {
        state.register_client_session(session.to_string()).unwrap()
    }

    fn session_epoch(state: &PreviewState, session: &str) -> Option<u64> {
        state
            .known_client_sessions
            .iter()
            .find_map(|(session_id, epoch)| (session_id == session).then_some(*epoch))
    }

    fn begin(
        state: &mut PreviewState,
        session: &str,
        request: &str,
        generation: u64,
    ) -> PreviewToken {
        let epoch = session_epoch(state, session).unwrap_or_else(|| register(state, session));
        state
            .begin(
                session.to_string(),
                Some(epoch),
                request.to_string(),
                generation,
            )
            .unwrap()
    }

    fn cancel(state: &mut PreviewState, session: &str, request: &str, generation: u64) -> bool {
        let epoch = session_epoch(state, session);
        state.cancel(session, epoch, request, generation)
    }

    #[test]
    fn newer_preview_request_supersedes_older_generation() {
        let mut state = preview_state();
        let older = begin(&mut state, "session-a", "older", 1);
        assert!(state.is_current(&older));

        let newer = begin(&mut state, "session-a", "newer", 2);
        assert!(!state.is_current(&older));
        assert!(state.is_current(&newer));
    }

    #[test]
    fn stale_preview_cancel_does_not_cancel_current_request() {
        let mut state = preview_state();
        begin(&mut state, "session-a", "older", 1);
        let current = begin(&mut state, "session-a", "current", 2);

        assert!(!cancel(&mut state, "session-a", "older", 1));
        assert!(state.is_current(&current));
        assert!(cancel(&mut state, "session-a", "current", 2));
        assert!(!state.is_current(&current));
        assert!(!cancel(&mut state, "session-a", "current", 2));
    }

    #[test]
    fn stale_cancel_with_reused_request_id_does_not_cancel_new_generation() {
        let mut state = preview_state();
        begin(&mut state, "session-a", "same-id", 10);
        let current = begin(&mut state, "session-a", "same-id", 11);

        assert!(!cancel(&mut state, "session-a", "same-id", 10));
        assert!(state.is_current(&current));
        assert!(cancel(&mut state, "session-a", "same-id", 11));
    }

    #[test]
    fn preview_pid_registration_and_release_require_exact_owner() {
        let mut state = preview_state();
        let older = begin(&mut state, "session-a", "older", 1);
        assert!(state.register_pid(&older, 101));

        let current = begin(&mut state, "session-a", "current", 2);
        assert!(!state.register_pid(&older, 202));
        assert!(!state.release(&older, Some(101)));
        assert!(state.is_current(&current));
        assert!(state.register_pid(&current, 303));
        assert!(!state.release(&current, Some(404)));
        assert!(state.release(&current, Some(303)));
    }

    #[test]
    fn cancel_before_begin_prevents_request_resurrection() {
        let mut state = preview_state();
        let epoch = register(&mut state, "session-a");

        assert!(cancel(&mut state, "session-a", "cancelled", 3));
        assert!(state
            .begin(
                "session-a".to_string(),
                Some(epoch),
                "cancelled".to_string(),
                3,
            )
            .is_none());
        assert!(!cancel(&mut state, "session-a", "cancelled", 3));
        assert!(state.active.is_none());
    }

    #[test]
    fn out_of_order_begin_cannot_replace_newer_client_generation() {
        let mut state = preview_state();
        let newer = begin(&mut state, "session-a", "newer", 8);
        let epoch = session_epoch(&state, "session-a").unwrap();

        assert!(state
            .begin("session-a".to_string(), Some(epoch), "older".to_string(), 7,)
            .is_none());
        assert!(state.is_current(&newer));
    }

    #[test]
    fn newer_cancel_tombstone_supersedes_active_older_request() {
        let mut state = preview_state();
        let older = begin(&mut state, "session-a", "older", 4);
        let epoch = session_epoch(&state, "session-a").unwrap();

        assert!(cancel(&mut state, "session-a", "future", 5));
        assert!(!state.is_current(&older));
        assert!(state
            .begin(
                "session-a".to_string(),
                Some(epoch),
                "future".to_string(),
                5,
            )
            .is_none());
    }

    #[test]
    fn a_new_renderer_session_can_restart_generation_at_one() {
        let mut state = preview_state();
        let old = begin(&mut state, "session-a", "old", 20);
        let current = begin(&mut state, "session-b", "new", 1);

        assert!(!state.is_current(&old));
        assert!(state.is_current(&current));
    }

    #[test]
    fn old_registered_session_cancel_cannot_touch_new_renderer_request() {
        let mut state = preview_state();
        begin(&mut state, "session-a", "old", 20);
        let current = begin(&mut state, "session-b", "new", 1);

        assert!(!cancel(&mut state, "session-a", "old", 20));
        assert!(state.is_current(&current));
        assert!(cancel(&mut state, "session-b", "new", 1));
    }

    #[test]
    fn cancel_before_begin_is_scoped_to_its_renderer_session() {
        let mut state = preview_state();
        let epoch_a = register(&mut state, "session-a");

        assert!(cancel(&mut state, "session-a", "cancelled", 3));
        assert!(state
            .begin(
                "session-a".to_string(),
                Some(epoch_a),
                "cancelled".to_string(),
                3,
            )
            .is_none());
        assert_eq!(
            begin(&mut state, "session-b", "new", 1).client_generation,
            1
        );
    }

    #[test]
    fn unknown_session_begin_and_cancel_do_not_mutate_current_request() {
        let mut state = preview_state();
        let current = begin(&mut state, "session-current", "current", 1);

        assert!(state
            .begin(
                "session-unknown".to_string(),
                Some(999),
                "late".to_string(),
                999,
            )
            .is_none());
        assert!(!state.cancel("session-unknown", Some(999), "late", 999));
        assert!(state.is_current(&current));
        assert_eq!(
            state.current_client_session_id.as_deref(),
            Some("session-current")
        );
    }

    #[test]
    fn registering_an_old_session_is_idempotent_and_does_not_reactivate_it() {
        let mut state = preview_state();
        let old_epoch = register(&mut state, "session-old");
        begin(&mut state, "session-old", "old", 10);
        let current = begin(&mut state, "session-current", "current", 1);

        assert_eq!(register(&mut state, "session-old"), old_epoch);
        assert!(state.is_current(&current));
        assert_eq!(
            state.current_client_session_id.as_deref(),
            Some("session-current")
        );
    }

    #[test]
    fn session_registry_never_forgets_old_epochs() {
        let mut state = preview_state();
        let first_epoch = register(&mut state, "session-0");
        for index in 1..32 {
            register(&mut state, &format!("session-{index}"));
        }
        let current_epoch = session_epoch(&state, "session-31").unwrap();
        let current = state
            .begin(
                "session-31".to_string(),
                Some(current_epoch),
                "current".to_string(),
                1,
            )
            .unwrap();

        assert_eq!(register(&mut state, "session-0"), first_epoch);
        assert!(state
            .begin(
                "session-0".to_string(),
                Some(first_epoch),
                "late".to_string(),
                999,
            )
            .is_none());
        assert!(!state.cancel("session-0", Some(first_epoch), "late", 999));
        assert!(state.is_current(&current));
    }

    #[test]
    fn legacy_requests_cannot_replace_a_registered_modern_session() {
        let mut state = preview_state();
        assert!(state
            .register_client_session(LEGACY_PREVIEW_CLIENT_SESSION_ID.to_string())
            .is_err());
        let legacy = state
            .begin(
                LEGACY_PREVIEW_CLIENT_SESSION_ID.to_string(),
                None,
                "legacy".to_string(),
                1,
            )
            .unwrap();
        assert!(state.is_current(&legacy));

        let modern = begin(&mut state, "session-modern", "modern", 1);
        assert!(!state.cancel(LEGACY_PREVIEW_CLIENT_SESSION_ID, None, "legacy", 2));
        assert!(state.is_current(&modern));
    }

    #[test]
    fn preview_response_echoes_request_id() {
        let payload =
            attach_preview_request_id(json!({ "preview_src": "data:image/svg+xml" }), "request-7")
                .unwrap();

        assert_eq!(payload["request_id"], "request-7");
    }

    #[test]
    fn preview_pipe_drain_handles_payload_larger_than_windows_pipe_buffer() {
        let payload = vec![b'x'; 256 * 1024];
        let reader = std::io::Cursor::new(payload.clone());

        let drained = join_preview_pipe(drain_preview_pipe(reader, "test").unwrap()).unwrap();

        assert_eq!(drained, payload);
    }

    #[test]
    fn preview_pipe_drain_timeout_is_bounded() {
        let (release, receiver) = mpsc::channel();
        let drain = drain_preview_pipe(BlockingReader { release: receiver }, "blocked").unwrap();
        let started = Instant::now();

        let error = join_preview_pipe_with_timeout(drain, Duration::from_millis(20)).unwrap_err();

        assert!(error.contains("Timed out waiting"));
        assert!(started.elapsed() < Duration::from_secs(1));
        drop(release);
    }

    #[test]
    fn active_sidecar_registration_is_removed_on_drop() {
        let pid = u32::MAX - 1;
        {
            let _active = ActiveSidecarProcess::new(pid);
            assert!(ACTIVE_SIDECAR_PIDS
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner())
                .contains(&pid));
        }
        assert!(!ACTIVE_SIDECAR_PIDS
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .contains(&pid));
    }

    #[test]
    fn shutdown_process_selection_preserves_cleanup_tree() {
        let parents = HashMap::from([(10, 1), (11, 10), (20, 1), (21, 20)]);

        let selected = descendant_processes_to_terminate(&parents, 1, &[20]);

        assert_eq!(selected, vec![(11, 2), (10, 1)]);
    }

    #[test]
    fn settings_payload_translates_flat_frontend_shape_to_yaml_fragment() {
        let input = json!({
            "convertWorkers": 3,
            "odaTimeoutSeconds": 120,
            "cacheCapBytes": 2147483648u64,
            "stageTelemetryEnabled": true,
        });
        let payload = normalize_settings_payload(&input).expect("payload should normalize");
        assert_eq!(payload["ingest"]["convert_workers"], json!(3));
        assert_eq!(payload["ingest"]["oda_timeout_seconds"], json!(120));
        assert_eq!(payload["runtime"]["stage_telemetry"], json!(true));
        assert_eq!(
            payload["runtime"]["cache_cap_bytes"],
            json!(2_147_483_648u64)
        );
    }

    #[test]
    fn settings_default_payload_is_recognized_as_default() {
        let defaults = json!({
            "ingest": {
                "convert_workers": 0,
                "oda_timeout_seconds": 300,
            },
            "runtime": {
                "stage_telemetry": false,
            },
        });
        assert!(is_default_settings_payload(&defaults));
    }

    #[test]
    fn settings_non_default_payload_is_not_default() {
        let mut payload = json!({
            "ingest": {
                "convert_workers": 0,
                "oda_timeout_seconds": 300,
            },
            "runtime": {
                "stage_telemetry": false,
            },
        });
        payload["ingest"]["convert_workers"] = json!(1);
        assert!(!is_default_settings_payload(&payload));
    }

    #[test]
    fn settings_reject_out_of_range_timeout() {
        let oversized = json!({"odaTimeoutSeconds": 86401u64});
        let err = normalize_settings_payload(&oversized).expect_err("timeout should be rejected");
        assert!(err.contains("oda_timeout_seconds"));
    }

    #[test]
    fn settings_null_cache_cap_is_preserved() {
        let input = json!({
            "convertWorkers": 0,
            "odaTimeoutSeconds": 300,
            "cacheCapBytes": null,
            "stageTelemetryEnabled": false,
        });
        let payload = normalize_settings_payload(&input).expect("payload should normalize");
        assert!(payload
            .get("runtime")
            .and_then(|v| v.get("cache_cap_bytes"))
            .is_none());
        assert!(is_default_settings_payload(&payload));
    }
}
