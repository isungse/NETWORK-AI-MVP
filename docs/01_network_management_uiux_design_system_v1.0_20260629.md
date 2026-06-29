# Network Management UI/UX Design System

```yaml
file_name: 01_network_management_uiux_design_system_v1.0_20260629.md
project: Internal Backbone & L2 Switch Management System
version: v1.0
date: 2026-06-29
purpose: Enterprise SaaS style UI/UX design refactoring prompt
```

---

# 1. Role

You are a senior enterprise SaaS UI/UX architect and product designer.

You are designing a web-based system for diagnosing, monitoring, and maintaining internal backbone switches and L2 switches.

The system will be used by hospital IT staff and network administrators.
The design must prioritize operational clarity, readability, consistency, and safety over decorative visuals.

The final result must feel like a professional enterprise network management console, not a general admin template.

---

# 2. Product Context

This system is used for:

- Backbone switch status monitoring
- L2 switch status monitoring
- Device inventory management
- Port/interface status checking
- VLAN and MAC address lookup
- Read-only diagnostic execution
- Alert and event review
- Maintenance history tracking
- Audit log review

The user may need to make decisions quickly during network issues.
Therefore, the UI must help the operator identify abnormal devices, ports, and diagnostic results with minimal visual noise.

---

# 3. Core Design Direction

The UI/UX must follow a modern, minimalist enterprise SaaS style with a network operations console mindset.

The design should feel:

- Professional
- Stable
- Minimal
- Trustworthy
- Data-focused
- Easy to scan
- Operationally safe

Avoid:

- Consumer-style dashboards
- Excessive gradients
- Glassmorphism
- Neon colors
- Large decorative illustrations
- Unnecessary animations
- Oversized cards
- Unclear icon-only interactions
- Flashy primary colors

The design goal is not to make the system look fancy.
The goal is to help hospital IT administrators quickly understand network status and safely perform diagnostic workflows.

---

# 4. Layout & Grid System

Use a strict and consistent layout system.

Recommended base layout:

- Left sidebar navigation
- Top header
- Main content area
- Optional right-side detail panel
- Tables, cards, logs, and diagnostic panels inside the main area

Recommended spacing:

- Page padding: 24px
- Section gap: 16px to 24px
- Card padding: 20px or 24px
- Table cell padding: 8px to 12px
- Compact table cell padding: 6px to 8px
- Form field gap: 12px to 16px

Use an 8px grid system.

The layout should support data-heavy screens without feeling crowded.

---

# 5. Page Structure

Use the following page structure as the standard.

```text
┌──────────────────────────────────────────────────────────────┐
│ Top Header                                                   │
├───────────────┬──────────────────────────────────────────────┤
│ Sidebar       │ Main Content                                 │
│               │                                              │
│ Navigation    │ Page Title                                   │
│ Menu          │ Filter Bar                                   │
│               │ Summary Cards                                │
│               │ Main Table / Matrix / Logs                   │
└───────────────┴──────────────────────────────────────────────┘
```

For detail-heavy screens, use a right-side detail panel.

```text
┌───────────────┬───────────────────────────────┬──────────────┐
│ Sidebar       │ Main Content                   │ Detail Panel │
└───────────────┴───────────────────────────────┴──────────────┘
```

Recommended sizes:

- Sidebar: 220px to 240px
- Top header: 56px to 64px
- Main content padding: 24px
- Right detail panel: 420px
- Table row height: 40px default
- Compact table row height: 32px to 36px

---

# 6. Color System

Use a calm grayscale and muted blue-based enterprise palette.

Recommended base colors:

```text
Page Background:     #F5F7FA or #F6F8FB
Card Background:     #FFFFFF
Main Border:         #E2E8F0
Subtle Divider:      #EDF2F7
Primary Text:        #111827
Secondary Text:      #4B5563
Muted Text:          #6B7280
Disabled Text:       #9CA3AF
```

Recommended accent direction:

```text
Primary Action:      Muted Navy / Blue Gray
Information:         Muted Blue
Success:             Muted Green
Warning:             Amber
Critical/Error:      Muted Red
Unknown/Disabled:    Gray
Maintenance:         Blue Gray
```

Important rules:

- Do not use bright or highly saturated colors as the main theme.
- Status colors must be used only for meaning, not decoration.
- Never rely on color alone.
- Always pair status colors with text labels or icons.
- Keep the background bright, clean, and spacious.

---

# 7. Typography

Use clean, modern, highly readable typography.

Recommended font stack:

```css
font-family:
  Pretendard, Inter, "Noto Sans KR", "Apple SD Gothic Neo", system-ui,
  sans-serif;
```

For CLI output, logs, IP addresses, MAC addresses, and command results:

```css
font-family: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
```

Recommended typography scale:

```text
Page Title:          22px to 26px / Semibold
Section Title:       16px to 18px / Semibold
Card Title:          15px to 16px / Semibold
Body Text:           14px to 15px
Table Text:          13px to 14px
Helper Text:         12px to 13px
CLI / Log Text:      12px to 13px / Monospace
```

Line height:

```text
Body:                1.5
Table:               1.35 to 1.45
CLI / Logs:          1.45
```

Use tabular numbers for:

- Port numbers
- VLAN IDs
- IP address segments
- Latency
- Error counts
- Traffic values
- Uptime
- Percentages

---

# 8. Navigation Structure

Recommended main navigation:

```text
Dashboard
Devices
Backbone Switches
L2 Switches
Ports / Interfaces
VLANs
MAC Lookup
Diagnostics
Alerts / Events
Maintenance History
Audit Logs
Settings
```

Navigation rules:

- Keep the menu shallow.
- Avoid unnecessary deep nesting.
- Use clear labels.
- Group monitoring, diagnostics, and history logically.
- Highlight the active page clearly.
- Avoid icon-only navigation unless labels are also visible.

---

# 9. Dashboard Design

The dashboard must show the operational state at a glance.

Recommended dashboard sections:

## 9.1 Overall Network Health

Show:

- Total devices
- Normal devices
- Warning devices
- Critical devices
- Down devices
- Unreachable devices
- Last sync time

## 9.2 Backbone Switch Status

Show:

- Device name
- Management IP
- Model
- Role
- Uptime
- CPU / Memory if available
- Last checked time
- Current status

## 9.3 L2 Switch Summary

Show:

- Location
- Device count
- Online count
- Offline count
- Warning count
- Port utilization
- Recent alerts

## 9.4 Recent Alerts

Show:

- Severity
- Device
- Interface
- Message
- Timestamp
- Status
- Owner if available

## 9.5 Recent Diagnostic Runs

Show:

- Requested by
- Device
- Diagnostic type
- Result
- Execution time
- Timestamp

Dashboard rules:

- Avoid large empty hero sections.
- Avoid decorative charts with no operational value.
- Prioritize abnormal conditions.
- Warning, Critical, Down, and Unknown states must be visible without scrolling.
- Normal data should not visually dominate the dashboard.

---

# 10. Device Inventory Table

The device inventory screen must be optimized for fast scanning and filtering.

Recommended columns:

```text
Status
Device Name
Management IP
Device Type
Vendor
Model
Location
Role
Uptime
Last Checked
Firmware / OS Version
Actions
```

Table alignment rules:

```text
Text values:         Left aligned
Numeric values:      Right aligned
Status values:       Left or center with badge
IP addresses:        Monospace
MAC addresses:       Monospace
Port numbers:        Tabular numeric
VLAN IDs:            Tabular numeric
Date/time values:    Consistent format
```

Table features:

- Search
- Status filter
- Device type filter
- Location filter
- Sort
- Column visibility control
- Compact density mode
- Export option if needed
- Row click to open detail panel
- Tooltip for truncated values

Design rules:

- The table should feel spreadsheet-like but not visually noisy.
- Avoid heavy borders on every cell.
- Use subtle row dividers.
- Use clear hover and selected states.
- Do not truncate important values without hover access.

---

# 11. Form & Inline Editing Design

Forms must be simple, structured, and safe.

Input fields inside tables should integrate seamlessly into cells using borderless or subtle-border styling.

Rules:

- Avoid heavy input borders inside dense tables.
- Use a clear focus state.
- Show validation messages inline.
- Use placeholder text only as helper text, not as a replacement for labels.
- Required fields must be clearly marked.
- Dangerous or sensitive fields must be visually separated.
- Use confirmation only for meaningful changes.

Recommended editing patterns:

```text
Simple metadata:       Inline editing
Detailed metadata:     Right-side drawer form
Risky action:          Confirmation modal
Bulk action:           Preview before apply
```

---

# 12. Status & Badge System

Every status must be represented consistently.

Recommended status labels:

```text
Normal
Info
Warning
Critical
Down
Unknown
Maintenance
Disabled
Resolved
```

Each status must include:

- Badge color
- Text label
- Optional icon or dot
- Tooltip explanation
- Consistent use across all screens

Never rely only on color.

Status badges must appear consistently in:

- Dashboard
- Device table
- Port table
- Port matrix
- Alert list
- Diagnostic result
- Maintenance history
- Audit logs
- Detail panel

---

# 13. Alert & Event Design

Alerts must help the operator prioritize work.

Recommended alert fields:

```text
Severity
Device
Interface
Message
First Detected Time
Last Detected Time
Status
Owner
Resolution Note
```

Alert rules:

- Critical alerts must stand out.
- Resolved alerts should be visually muted.
- Repeated alerts should be grouped when possible.
- Alert timestamps must be easy to compare.
- Normal state should not be mixed with active alerts.
- Default sorting should prioritize Down, Critical, and Warning.

---

# 14. Diagnostic Workflow Design

The diagnostic workflow must clearly separate read-only diagnostics from risky maintenance actions.

Recommended flow:

```text
1. Select device
2. Select port or diagnostic target
3. Select diagnostic purpose
4. Show command preview
5. User confirms execution
6. Run diagnostic
7. Show parsed summary
8. Allow raw CLI review
9. Save diagnostic history
```

Important rules:

- Default diagnostic commands must be read-only.
- Do not expose configuration-changing commands in the normal diagnostic flow.
- Show the target device clearly before execution.
- Show the target port clearly before execution.
- Show command risk level before execution.
- Save audit history after execution.
- Prevent accidental execution through unclear buttons.

---

# 15. Log & CLI Output Design

CLI outputs, diagnostic logs, and raw command results must use a dedicated readable viewer.

Required features:

- Monospace font
- Proper line height
- Copy button
- Search within output
- Expand / collapse
- Command-level grouping
- Error keyword highlight
- Warning keyword highlight
- Timestamp display
- Device display
- Command display
- Execution result status

Important rule:

Raw CLI output must not dominate the default screen.
Show parsed summary first and allow raw CLI expansion when needed.

---

# 16. Empty, Loading, and Error States

Design all system states carefully.

Empty state examples:

```text
No devices registered
No alerts found
No diagnostic results yet
No matching search results
No maintenance history
```

Loading state examples:

```text
Checking device status
Running diagnostic command
Loading logs
Loading topology
Syncing device data
```

Error state examples:

```text
Device unreachable
Authentication failed
Timeout
Unsupported command
Permission denied
Invalid response format
```

Error message rules:

- Keep messages clear and short.
- Provide the next possible action.
- Do not expose passwords, tokens, SNMP community strings, secrets, or credentials.
- Avoid vague messages such as “Something went wrong.”

---

# 17. Accessibility & Usability

The design must support long working sessions and accessibility.

Requirements:

- Sufficient color contrast
- Text labels in addition to color indicators
- Keyboard-friendly navigation
- Clear focus states
- Tooltips for technical abbreviations
- Desktop-first responsive design
- Tablet support where practical
- Avoid small click targets
- Avoid excessive animation
- Avoid hover-only critical information

---

# 18. Component Standards

Recommended components:

```text
Status Badge
Metric Card
Data Table
Filter Bar
Search Input
Right Detail Drawer
Command Preview Panel
CLI Log Viewer
Alert List
Port Matrix
Timeline
Audit Trail
Empty State
Confirmation Modal
Toast Notification
Breadcrumb
Tab Navigation
```

Component style rules:

- Use 1px borders.
- Use subtle shadows only when needed.
- Use 8px to 12px border radius.
- Use white cards on light gray background.
- Use muted dividers.
- Use consistent icon style.
- Keep table density compact but readable.
- Avoid mixing multiple font families.

---

# 19. Visual Style Rules

Use:

```text
Clean white cards
Bright neutral background
Muted borders
Subtle dividers
Minimal shadows
Consistent spacing
Readable tables
Meaningful status colors
Clear hierarchy
```

Avoid:

```text
Strong gradients
Neon colors
Excessive shadows
Oversized dashboard cards
Decorative illustrations
Unnecessary animations
Dense borders on every cell
Inconsistent icon styles
Unclear buttons
```

---

# 20. Final Refactoring Goal

Refactor the current UI into a professional enterprise network management console.

The final UI must help hospital IT administrators:

- Understand the current network status quickly
- Identify abnormal devices or ports
- Run safe diagnostics
- Review command results clearly
- Track maintenance history
- Reduce operational mistakes
- Work comfortably with large amounts of network data

Prioritize:

```text
Clarity
Safety
Consistency
Readability
Operational efficiency
Fast decision-making
```

The final design must feel suitable for an internal hospital IT infrastructure environment where stability and accuracy are more important than decorative design.

```

```
