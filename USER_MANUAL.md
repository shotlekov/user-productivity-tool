# User Productivity Tool - Complete User Manual

## Table of Contents
1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Understanding the Interface](#understanding-the-interface)
4. [Step-by-Step Operation Guide](#step-by-step-operation-guide)
5. [Detailed Element Descriptions](#detailed-element-descriptions)
6. [CSV File Format Requirements](#csv-file-format-requirements)
7. [Understanding the Reports](#understanding-the-reports)
8. [Troubleshooting](#troubleshooting)
9. [Keyboard Shortcuts](#keyboard-shortcuts)

---

## Introduction

The **User Productivity Tool** is a desktop application that helps you analyze how users spend their time on different actions. It reads CSV files containing user activity logs, calculates productivity scores based on configurable weights, and generates detailed reports in Markdown format.

### What This Tool Does
- **Loads** user action logs from CSV files
- **Calculates** how long users spend on each action
- **Weights** different actions based on importance (e.g., "Ingest clip" might be worth more than "Mark POI as Done")
- **Ranks** users by productivity score
- **Exports** everything to a Markdown (.md) file you can open in any text editor

### Who Should Use This
- Team leads tracking productivity
- Managers analyzing workflow efficiency
- Anyone who needs to understand how time is spent across different tasks

---

## Getting Started

### System Requirements
- **Windows**: Download the `.exe` file and double-click to run
- **Linux/Mac**: Python 3.10+ with tkinter installed
  - Ubuntu/Debian: `sudo apt install python3-tk`
  - Fedora: `sudo dnf install python3-tkinter`
  - Mac: `brew install python-tk` (usually included with Python)

### Launching the Tool

**Option 1: GUI Mode (Recommended for most users)**
```bash
python3 user_productivity_tool.py --gui
```
Or simply double-click the executable on Windows.

**Option 2: Command Line Mode**
```bash
python3 user_productivity_tool.py --input your_data.csv --output report.md
```

---

## Understanding the Interface

The GUI has **5 main sections** arranged in cards:

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. INPUT CARD          │ 2. ACTION WEIGHTS CARD                 │
│    - CSV file picker   │    - List of actions with checkboxes   │
│    - Skip threshold    │    - Weight sliders/inputs             │
│    - Theme toggle      │                                        │
├────────────────────────┼────────────────────────────────────────┤
│ 3. USERS CARD          │ 4. RESULTS TABS                        │
│    - User list         │    - Ranking: Sorted productivity      │
│    - Select All/Clear  │    - Action Details: Full breakdown    │
│                        │    - Markdown: Full report text        │
│                        │    - Info: Documentation & logic       │
├────────────────────────┴────────────────────────────────────────┤
│ 5. BOTTOM BAR                                                    │
│    - Generate Report button    - Export Markdown button          │
│    - Status message area                                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Operation Guide

### Phase 1: Load Your CSV File

**Step 1.1 - Open the Tool**
- Launch the application using `--gui` flag or the Windows executable
- You'll see the main window with empty cards

**Step 1.2 - Select Your CSV File**
1. Look at the **Input Card** (top-left)
2. Click the **"Browse..."** button next to "CSV File"
3. Navigate to your CSV file and select it
4. The file path will appear in the text box

**Step 1.3 - Verify the File Loaded**
- The status bar (bottom) will show: "Loaded X actions, Y users from [filename]"
- The **Action Weights Card** will populate with actions found in your CSV
- The **Users Card** will populate with usernames found in your CSV

> **Tip**: The tool automatically detects CSV delimiters (comma, semicolon, tab, pipe). It also handles UTF-8 BOM encoding.

### Phase 2: Configure Calculation Parameters

**Step 2.1 - Set the Skip Threshold (Important!)**
- **Location**: Input Card → "Skip Threshold (minutes)"
- **Default**: 5 minutes
- **What it does**: Ignores gaps between actions longer than this threshold
- **Why it matters**: If a user takes a 30-minute lunch break, you don't want that counted as "work time"
- **Adjust**: Increase if your workflow has longer natural breaks; decrease for tighter tracking

**Step 2.2 - Choose Which Actions to Include**
- **Location**: Action Weights Card
- **Default**: All actions are checked (enabled)
- **What to do**: Uncheck actions you don't want in the calculation
- **Example**: Uncheck "Meeting" or "Break" if you only want productive work actions

**Step 2.3 - Adjust Action Weights**
- **Location**: Action Weights Card → Weight column
- **Default weights** (higher = more important):
  - Ingest clip: 5.0
  - Edit clip: 4.0
  - Update detect: 2.5
  - Deactivate clip & delete detects: 2.5
  - Mark POI as Done: 1.0
- **How to change**: Click the weight number and type a new value
- **Guideline**: Set weights based on business value or time investment

**Step 2.4 - Select Users to Analyze**
- **Location**: Users Card
- **Default**: All users selected
- **What to do**: Uncheck users you want to exclude from the report
- **Bulk actions**: Use "Select All" or "Clear All" buttons

**Step 2.5 - Choose Theme (Optional)**
- **Location**: Input Card → "Theme" dropdown
- **Options**: Light / Dark
- **Effect**: Changes the entire application color scheme instantly

### Phase 3: Generate the Report

**Step 3.1 - Click "Generate Report"**
- **Location**: Bottom bar, left side
- **What happens**: 
  - Button shows "Generating..." and becomes disabled
  - Processing happens in background (UI stays responsive)
  - Status bar shows progress

**Step 3.2 - Wait for Completion**
- Typical time: 1-5 seconds depending on CSV size
- Status bar will show: "Report generated successfully"
- The **Results Tabs** will populate with data

**Step 3.3 - Review the Results**
Click through each tab:

| Tab | What You'll See |
|-----|-----------------|
| **Ranking** | Users sorted by productivity score (highest first) |
| **Action Details** | Detailed breakdown per user per action |
| **Markdown** | Complete report in Markdown format |
| **Info** | Documentation about calculations and logic |

### Phase 4: Export to Markdown File

**Step 4.1 - Click "Export Markdown"**
- **Location**: Bottom bar, right side (next to Generate Report)
- **What happens**: File save dialog opens

**Step 4.2 - Choose Save Location**
1. Navigate to desired folder
2. Enter filename (e.g., `productivity_report_2024.md`)
3. Click **Save**

**Step 4.3 - Verify Export**
- Status bar shows: "Markdown exported to [path]"
- Open the file in any text editor (VS Code, Notepad, Obsidian, etc.)
- The file contains the complete report with all tables and formatting

---

## Detailed Element Descriptions

### Input Card Elements

| Element | Description | Default | Notes |
|---------|-------------|---------|-------|
| **CSV File** | Path to your input CSV file | Empty | Click "Browse..." to select |
| **Browse... Button** | Opens file picker dialog | - | Supports .csv files |
| **Skip Threshold (minutes)** | Maximum gap between actions to count as continuous work | 5 | Gaps longer than this are ignored |
| **Theme** | Application color scheme | Light | Light/Dark toggle, applies instantly |

### Action Weights Card Elements

| Element | Description | Default | Notes |
|---------|-------------|---------|-------|
| **Action Name** | Name of the action from CSV | From CSV | Read-only, shows all unique actions |
| **Enabled Checkbox** | Whether to include this action in calculations | Checked | Uncheck to exclude |
| **Weight Input** | Numerical weight for this action | See defaults | Higher = more important. Must be ≥ 0 |
| **Select All Actions** | Button to check all action checkboxes | - | Convenience button |
| **Clear All Actions** | Button to uncheck all action checkboxes | - | Convenience button |

#### Default Action Weights (Built-in)
| Action | Weight | Rationale |
|--------|--------|-----------|
| Ingest clip | 5.0 | High-value, complex task |
| Edit clip | 4.0 | Core production work |
| Update detect | 2.5 | Maintenance task |
| Deactivate clip & delete detects | 2.5 | Cleanup task |
| Mark POI as Done | 1.0 | Quick administrative task |

> **Custom Actions**: If your CSV contains actions not in the default list, they appear with weight 1.0. You can adjust them like any other action.

### Users Card Elements

| Element | Description | Default | Notes |
|---------|-------------|---------|-------|
| **Username** | User identifier from CSV | From CSV | Read-only |
| **Enabled Checkbox** | Whether to include this user in report | Checked | Uncheck to exclude |
| **Select All Users** | Button to check all user checkboxes | - | Convenience button |
| **Clear All Users** | Button to uncheck all user checkboxes | - | Convenience button |

### Results Tabs

#### Ranking Tab
Shows users sorted by **Productivity Score** (highest first).

| Column | Meaning |
|--------|---------|
| **Rank** | Position in ranking (1 = best) |
| **User** | Username |
| **Total Actions** | Count of all actions performed |
| **Weighted Total** | Sum of (action count × action weight) |
| **Active Days** | Number of days user had activity |
| **Weighted Daily Volume** | Weighted actions per active day |
| **Volume Delta** | % difference from team average volume |
| **Speed Delta** | % difference from team average speed |
| **Avg Duration** | Average time per action (MM:SS.mmm) |
| **Score** | Combined productivity score (volume × speed × 100) |

#### Action Details Tab
Detailed breakdown showing every user-action combination with:
- Average duration
- Sample count (how many times measured)
- Per-user statistics

#### Markdown Tab
Complete report as formatted Markdown text. This is exactly what gets exported to file.

#### Info Tab
Reference documentation including:
- Calculation formulas
- Weight explanations
- CSV format requirements
- Version information

### Bottom Bar Elements

| Element | Description |
|---------|-------------|
| **Generate Report** | Starts the calculation process |
| **Export Markdown** | Saves the Markdown tab content to a file |
| **Status Area** | Shows current state, errors, or success messages |

---

## CSV File Format Requirements

### Required Columns
Your CSV **must** have these columns (case-insensitive, flexible names):

| Required Data | Accepted Column Names |
|---------------|----------------------|
| **Date** | `day`, `date` |
| **Time** | `hour`, `time` |
| **Username** | `username`, `user`, `user_name` |
| **Action** | `action` |

### Date/Time Formats Supported
| Format | Example |
|--------|---------|
| DD.MM.YYYY HH:MM:SS | 15.01.2024 09:30:00 |
| YYYY-MM-DD HH:MM:SS | 2024-01-15 09:30:00 |
| YYYY-MM-DD HH:MM | 2024-01-15 09:30 |

### Delimiters Supported
- Comma (`,`) - standard CSV
- Semicolon (`;`) - European CSV
- Tab (`\t`) - TSV files
- Pipe (`|`) - Pipe-delimited

### Example Valid CSV
```csv
day,time,username,action
2024-01-15,09:00:00,alice,Ingest clip
2024-01-15,09:15:00,alice,Edit clip
2024-01-15,09:45:00,bob,Update detect
2024-01-15,10:00:00,alice,Mark POI as Done
```

### Automatic Filtering
The tool **automatically excludes**:
- Rows where username is "system" (case-insensitive)
- Rows with missing action or invalid date/time
- Duplicate rows (same user, same day, same time, same action)

---

## Understanding the Reports

### How Productivity Score Is Calculated

The score combines **two factors**:

```
Productivity Score = Volume Factor × Speed Factor × 100
```

#### Volume Factor
- Compares user's **weighted daily action volume** to team average
- `Volume Factor = User's Weighted Daily Volume / Team Average Weighted Daily Volume`
- > 1.0 means user does more weighted work per day than average
- < 1.0 means user does less

#### Speed Factor
- Compares user's **action speed** to team average (weighted by action importance)
- `Speed Factor = Weighted Average of (Team Avg Duration / User Avg Duration)`
- > 1.0 means user is faster than average
- < 1.0 means user is slower than average

#### Example Interpretation
| Score | Meaning |
|-------|---------|
| 150 | 50% more productive than average |
| 100 | Exactly average |
| 75 | 25% less productive than average |

### What "Skip Threshold" Actually Does

When calculating time between actions:
1. Sort all actions by user, then by date/time
2. For each consecutive pair by same user on same day:
   - Calculate time difference
   - If difference ≤ threshold: count as work time
   - If difference > threshold: ignore (assumed break/idle)
   - If difference ≤ 0: ignore (duplicate or out of order)

**Example with 5-minute threshold:**
```
09:00 - Ingest clip
09:10 - Edit clip        → 10 min gap → COUNTED
09:15 - Update detect    → 5 min gap  → COUNTED
10:00 - Ingest clip      → 45 min gap → IGNORED (lunch?)
10:05 - Edit clip        → 5 min gap  → COUNTED
```

---

## Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| **"CSV is missing required columns"** | Check column names match: day/date, hour/time, username/user, action |
| **"No data loaded"** | Verify CSV has data rows (not just headers), check encoding (try UTF-8) |
| **Users/actions not appearing** | Click "Generate Report" first - lists populate after CSV load |
| **Report shows zeros** | Check skip threshold isn't too low, verify actions are enabled |
| **Export button disabled** | Must generate report first |
| **GUI won't start on Linux** | Install tkinter: `sudo apt install python3-tk` |

### CSV Encoding Issues
- Tool uses `utf-8-sig` encoding (handles BOM automatically)
- If special characters appear garbled, re-save CSV as UTF-8 in your editor

### Large Files
- Tool processes in background thread - UI stays responsive
- For files > 100k rows, generation may take 10-30 seconds
- Status bar shows progress

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Browse for CSV file |
| `Ctrl+G` | Generate Report |
| `Ctrl+E` | Export Markdown |
| `Ctrl+Q` | Quit application |
| `Tab` | Navigate between fields |
| `Space` | Toggle checkboxes (when focused) |
| `Enter` | Activate focused button |

---

## Command Line Reference

For automation or scripting:

```bash
# Basic usage
python3 user_productivity_tool.py --input data.csv

# With options
python3 user_productivity_tool.py \
  --input data.csv \
  --output report.md \
  --threshold-minutes 10 \
  --actions "Ingest clip,Edit clip" \
  --weight "Ingest clip=5.0" \
  --weight "Edit clip=4.0" \
  --users "alice,bob"

# Help
python3 user_productivity_tool.py --help
```

### CLI Options Table

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--gui` | - | Launch graphical interface | Off |
| `--input` | `-i` | Input CSV file path | Required |
| `--output` | `-o` | Output Markdown file path | Stdout |
| `--threshold-minutes` | `-t` | Skip threshold in minutes | 5.0 |
| `--actions` | `-a` | Comma-separated actions to include | All default |
| `--weight` | `-w` | Action weight as ACTION=NUMBER | Defaults |
| `--users` | `-u` | Comma-separated users to include | All |

---

## Tips for Best Results

1. **Clean your data first**: Remove test users, system accounts, and irrelevant actions before loading
2. **Set realistic thresholds**: 5 minutes works for most office work; adjust for your workflow
3. **Weight by business value**: Not just time - a 5-minute high-impact action may deserve higher weight than a 30-minute low-impact one
4. **Run regularly**: Weekly or monthly reports show trends better than one-time snapshots
5. **Share Markdown reports**: They open in any tool - GitHub, Notion, Obsidian, VS Code, browsers

---

## Version Information

- **Current Version**: 1.0
- **Python Requirement**: 3.10+
- **License**: Open source (personal and commercial use)
- **Repository**: https://github.com/shotlekov/user-productivity-tool

---

## Support

For issues, feature requests, or questions:
- GitHub Issues: https://github.com/shotlekov/user-productivity-tool/issues
- Check the **Info tab** in the application for built-in documentation

---

*This manual covers all features of the User Productivity Tool. For the most up-to-date information, check the application's Info tab or the GitHub repository.*