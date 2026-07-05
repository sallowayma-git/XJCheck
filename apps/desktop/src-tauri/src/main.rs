#[tauri::command]
fn desktop_analyze_session(_input_root: String, _session_id: Option<String>) -> Result<serde_json::Value, String> {
    Err("Native Python sidecar bridge is not wired yet. The frontend should fall back to mock session data.".into())
}

#[tauri::command]
fn desktop_list_recent_projects() -> Result<serde_json::Value, String> {
    Err("Native recent-project lookup is not wired yet. The frontend should fall back to mock project data.".into())
}

#[tauri::command]
fn desktop_load_result(_project_id: String) -> Result<serde_json::Value, String> {
    Err("Native result loading is not wired yet. The frontend should fall back to mock result data.".into())
}

#[tauri::command]
fn desktop_render_preview(
    _project_id: String,
    _issue_id: Option<String>,
    _sheet_id: Option<String>,
) -> Result<serde_json::Value, String> {
    Err("Native preview rendering is not wired yet. The frontend should fall back to mock preview data.".into())
}

#[tauri::command]
fn desktop_set_issue_status(
    _project_id: String,
    _issue_id: String,
    _status: String,
) -> Result<serde_json::Value, String> {
    Err("Native issue-status persistence is not wired yet. The frontend should fall back to mock status updates.".into())
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
