#!/usr/bin/env bash

# Robust script with error handling
set -euo pipefail

# Function to print error messages to stderr
err() {
    echo "[ERROR] $(date '+%Y-%m-%d %T'): $*" >&2
}

# Function to print info messages
info() {
    echo "[INFO] $(date '+%Y-%m-%d %T'): $*"
}

# Resolve the script's directory
resolve_script_dir() {
    # Get the directory where this script resides
    local SOURCE="${BASH_SOURCE[0]}"
    
    # Resolve $SOURCE until the file is no longer a symlink
    while [ -h "$SOURCE" ]; do
        local DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
        SOURCE="$(readlink "$SOURCE")"
        # If $SOURCE was a relative symlink, resolve it relative to the path
        [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
    done
    
    # Get the final directory path
    SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    echo "$SCRIPT_DIR"
}

# Activate virtual environment if it exists
activate_venv() {
    local venv_path="$1/.venv"
    
    if [[ -d "$venv_path" ]]; then
        # Check for activation script (supports both venv and virtualenv)
        if [[ -f "$venv_path/bin/activate" ]]; then
            info "Activating virtual environment from $venv_path"
            # shellcheck source=/dev/null
            source "$venv_path/bin/activate"
        elif [[ -f "$venv_path/Scripts/activate" ]]; then
            info "Activating virtual environment from $venv_path (Windows)"
            # shellcheck source=/dev/null
            source "$venv_path/Scripts/activate"
        else
            err "Virtual environment found but no activation script detected"
            return 1
        fi
    else
        info "No virtual environment found at $venv_path, using system Python"
    fi
}

# Main execution
main() {
    info "Starting mutt daemon..."
    
    # Resolve script directory
    local script_dir
    script_dir=$(resolve_script_dir)
    info "Script directory: $script_dir"
    
    # Change to script directory
    cd "$script_dir" || {
        err "Failed to change to directory: $script_dir"
        exit 1
    }
    
    # Activate virtual environment if it exists
    activate_venv "$script_dir"
    
    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        err "python3 command not found. Please install Python 3."
        exit 1
    fi
    
    # Check if config file exists
    local config_path="config/mutt_config.yaml"
    if [[ ! -f "$config_path" ]]; then
        err "Config file not found: $config_path"
        info "Current directory: $(pwd)"
        info "Available config files:"
        find . -name "*.yaml" -o -name "*.yml" 2>/dev/null | head -10
        exit 1
    fi
    
    # Execute the mutt daemon
    info "Executing: python3 -m mutt.daemon --config $config_path"
    exec python3 -m mutt.daemon --config "$config_path"
}

# Run main function
main "$@"
