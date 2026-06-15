#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::{Path, PathBuf};
use std::process::Command;

#[tauri::command]
fn create_test_project() -> Result<String, String> {
    let repo_root = find_repo_root()?;
    run_real_uat(&repo_root, "create")?;
    read_desktop_state(&repo_root)
}

#[tauri::command]
fn read_test_project_projection() -> Result<String, String> {
    let repo_root = find_repo_root()?;
    read_desktop_state(&repo_root)
}

#[tauri::command]
fn cleanup_test_project() -> Result<String, String> {
    let repo_root = find_repo_root()?;
    run_real_uat(&repo_root, "cleanup")?;
    Ok("{\"removed\":true}".to_string())
}

#[tauri::command]
fn save_project_init_draft(payload_json: String) -> Result<String, String> {
    let repo_root = find_repo_root()?;
    run_real_uat_with_payload(&repo_root, "save-init", &payload_json)?;
    read_desktop_state(&repo_root)
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            create_test_project,
            read_test_project_projection,
            cleanup_test_project,
            save_project_init_draft
        ])
        .run(tauri::generate_context!())
        .expect("failed to run Nexus L1 Governance desktop UX test surface");
}

fn run_real_uat(repo_root: &Path, command_name: &str) -> Result<(), String> {
    run_real_uat_args(repo_root, command_name, &[])
}

fn run_real_uat_with_payload(repo_root: &Path, command_name: &str, payload_json: &str) -> Result<(), String> {
    run_real_uat_args(repo_root, command_name, &["--payload-json", payload_json])
}

fn run_real_uat_args(repo_root: &Path, command_name: &str, extra_args: &[&str]) -> Result<(), String> {
    let python = std::env::var("NEXUS_PYTHON").unwrap_or_else(|_| "python".to_string());
    let mut command = Command::new(python);
    command
        .current_dir(repo_root)
        .arg("-m")
        .arg("nexus.governance.real_uat")
        .arg(command_name)
        .arg("--repo-root")
        .arg(repo_root)
        .arg("--project-name")
        .arg("TestProject");
    for arg in extra_args {
        command.arg(arg);
    }
    let output = command
        .output()
        .map_err(|error| format!("failed to invoke local real UAT command: {error}"))?;
    if output.status.success() {
        return Ok(());
    }
    Err(format!(
        "real UAT command failed: {}",
        String::from_utf8_lossy(&output.stderr)
    ))
}

fn read_desktop_state(repo_root: &Path) -> Result<String, String> {
    let path = repo_root
        .join("verification")
        .join("4.21")
        .join("real-uat")
        .join("testproject")
        .join("desktop-state.json");
    std::fs::read_to_string(&path).map_err(|error| format!("failed to read real projection state {path:?}: {error}"))
}

fn find_repo_root() -> Result<PathBuf, String> {
    if let Ok(path) = std::env::var("NEXUS_REPO_ROOT") {
        let candidate = PathBuf::from(path);
        if is_repo_root(&candidate) {
            return Ok(candidate);
        }
    }
    let mut candidates = Vec::new();
    if let Ok(current) = std::env::current_dir() {
        candidates.push(current);
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            candidates.push(parent.to_path_buf());
        }
    }
    for start in candidates {
        for candidate in start.ancestors() {
            if is_repo_root(candidate) {
                return Ok(candidate.to_path_buf());
            }
        }
    }
    Err("could not locate Nexus repo root for real UAT test environment".to_string())
}

fn is_repo_root(path: &Path) -> bool {
    path.join("nexus")
        .join("governance")
        .join("real_uat.py")
        .exists()
}
