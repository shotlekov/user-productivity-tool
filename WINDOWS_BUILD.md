# Windows Build

This tool has no runtime dependencies beyond Python's standard library.

## Building the Executable

### Option A: Fully Automated Build (Recommended)

1. **Double-click `build_windows_exe.bat`.**
2. If Python is not installed on the machine, the script will **automatically download and install Python 3.14.7** silently.
3. The script creates a virtual environment, installs PyInstaller, and builds the executable.
4. Use `dist\UserProductivityTool.exe` — it is fully portable.

### Option B: Manual Build (if Python is already installed)

1. Install Python 3.10 or newer for Windows (from https://www.python.org/downloads/).
2. Open this folder on Windows.
3. Double-click `build_windows_exe.bat`.
4. Use `dist\UserProductivityTool.exe`.

The executable opens the GUI directly. The Python source copy is `user_productivity_tool.py`.

## Auto-Installation Details

When Python is not detected, the build script will:
- Download the official Python 3.14.7 installer from python.org
- Install silently with: `/quiet InstallAllUsers=1 PrependPath=1 InstallLauncher=1 Include_test=0 Include_venv=1`
- Add Python to the system PATH
- Clean up the installer file
- Proceed with the virtual environment and build

## Portability

The resulting executable:
- Requires **no Python installation** on the target machine
- Runs on any Windows 10/11 system (x64)
- Has zero runtime dependencies
- Is a single portable .exe file

---

# Linux Desktop Integration

## Quick Launch (Double-Click)

1. Make the launcher executable:
   ```bash
   chmod +x launch_gui.py
   ```

2. Double-click `launch_gui.py` in your file manager, or run:
   ```bash
   python3 launch_gui.py
   ```

## Application Menu Integration

The `user-productivity-tool.desktop` file integrates with your desktop environment:

```bash
# Install to application menu
mkdir -p ~/.local/share/applications
cp user-productivity-tool.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications/
```

After installation, "User Productivity Tool" appears in your application launcher/menu with the custom icon.

## Desktop Entry Details

The `.desktop` file:
- Launches `python3 /home/meto/workspace/productivity_rates/launch_gui.py`
- Uses `icon.png` for the application icon
- Runs without terminal (`Terminal=false`)
- Appears in Office/Utility categories

## Requirements

- Python 3.10+
- tkinter (usually included with Python, or install via `python3-tk` on Ubuntu/Debian)