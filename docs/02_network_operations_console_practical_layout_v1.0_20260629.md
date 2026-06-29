# Network Operations Console Practical Layout Extension

```yaml
file_name: 02_network_operations_console_practical_layout_v1.0_20260629.md
project: Internal Backbone & L2 Switch Management System
version: v1.0
date: 2026-06-29
purpose: Practical network operations console layout prompt
```

---

# 1. Role

You are a senior network operations UI/UX architect.

You are designing practical screens for a web-based system used to diagnose and maintain internal backbone switches and L2 switches.

The system must support real operational workflows, especially:

- Finding abnormal ports quickly
- Reviewing switch details without page switching
- Previewing diagnostic commands before execution
- Distinguishing alert severity
- Separating parsed diagnostic summaries from raw CLI output

The final UI must work as a real network operations console.

---

# 2. Required Core Screens

The following five UI patterns must be added and treated as core parts of the system:

```text
1. Port Matrix View
2. Right Detail Panel
3. Command Preview Before Execution
4. Alert Severity Badge System
5. Raw CLI / Parsed Summary Split View
```

These are not decorative features.
They are required operational features for network diagnosis and maintenance.

---

# 3. Port Matrix View

## 3.1 Purpose

The Port Matrix View allows the operator to see the status of all switch ports at a glance.

This is one of the most important screens because network administrators often begin troubleshooting from port status, link status, VLAN, and error counters.

## 3.2 Recommended Layout

```text
┌──────────────────────────────────────────────────────────────┐
│ Device: Core-SW-01   IP: 192.168.0.1   Status: Normal        │
├──────────────────────────────────────────────────────────────┤
│ Total Ports │ Up │ Down │ Error │ Disabled │ Trunk │ Access │
├──────────────────────────────────────────────────────────────┤
│ [01] [02] [03] [04] [05] [06] [07] [08] [09] [10] [11] [12] │
│ [13] [14] [15] [16] [17] [18] [19] [20] [21] [22] [23] [24] │
│ [25] [26] [27] [28] [29] [30] [31] [32] [33] [34] [35] [36] │
│ [37] [38] [39] [40] [41] [42] [43] [44] [45] [46] [47] [48] │
├──────────────────────────────────────────────────────────────┤
│ Selected Port Summary / Recent Errors / Last Change          │
└──────────────────────────────────────────────────────────────┘
```

## 3.3 Port Tile Design

Each port should be displayed as a small tile or compact button.

Each tile must show:

```text
Port number
Port name
Operational status
Admin status if needed
Access / Trunk mode
Error indicator if applicable
Selected state
```

Example:

```text
┌──────┐
│ Gi01 │
│ UP   │
└──────┘
```

Compact example:

```text
[Gi01 UP] [Gi02 UP] [Gi03 ERR] [Gi04 DOWN]
```

## 3.4 Port Status Colors

Use color only as a supporting signal.

```text
Up:             Muted Green
Down:           Red
Error:          Red or Amber
Disabled:       Gray
Trunk:          Blue Gray
Access:         Neutral
Maintenance:    Muted Blue
Unknown:        Gray
```

Every port tile must include text, not only color.

## 3.5 Port Matrix Features

The Port Matrix View must support:

```text
All port status overview
Click port to open right detail panel
Filter Error ports
Filter Down ports
Filter Disabled ports
Filter Access ports
Filter Trunk ports
Filter by VLAN
Search by port description
Highlight recently changed ports
Highlight ports with CRC errors
Highlight ports with input errors
Highlight ports with discards
Highlight long-term Down ports
Tooltip on hover
```

## 3.6 Tooltip Information

When the user hovers over a port, show:

```text
Port name
Status
VLAN
Mode
Speed / Duplex
Description
Last Change
CRC Error Count
Input Error Count
Connected MAC Count
```

## 3.7 Practical Design Rules

- Support 24-port, 48-port, and 52-port switches.
- The layout must not break when devices have different port counts.
- Prefer wrapping port groups over horizontal scrolling.
- Keep port tiles compact.
- Abnormal ports must be easy to find within 3 seconds.
- Avoid decorative topology graphics that reduce readability.
- Provide a table view alternative for detailed analysis.

---

# 4. Right Detail Panel

## 4.1 Purpose

The Right Detail Panel allows the operator to inspect device, port, VLAN, alert, and diagnostic details without leaving the current screen.

This prevents unnecessary page switching during troubleshooting.

## 4.2 Recommended Size

```text
Default width:       420px
Narrow screen:       360px
Wide screen:         Up to 480px
Optional mode:       Fullscreen detail view
```

## 4.3 Recommended Layout

```text
┌────────────────────────────┐
│ Port Gi1/0/24              │
│ Status: Warning            │
├────────────────────────────┤
│ Summary                    │
│ VLAN: 20                   │
│ Mode: Access               │
│ Speed: 1G Full             │
│ Last Change: 2026-06-29    │
├────────────────────────────┤
│ Health                     │
│ CRC Errors: 12             │
│ Input Errors: 3            │
│ Discards: 0                │
├────────────────────────────┤
│ Recent Diagnostics          │
│ show interface Gi1/0/24    │
│ show mac address-table     │
├────────────────────────────┤
│ Actions                    │
│ [Run Diagnostic]           │
│ [View Raw CLI]             │
└────────────────────────────┘
```

## 4.4 Recommended Tabs

Use tabs inside the detail panel.

```text
Summary
Health
VLAN / MAC
Diagnostics
Alerts
History
Raw CLI
```

## 4.5 Device Detail Content

When a device is selected, show:

```text
Device Name
Management IP
Vendor
Model
OS / Firmware Version
Location
Role
Uptime
Reachability
CPU Usage if available
Memory Usage if available
Last Checked Time
Recent Alerts
Recent Diagnostics
```

## 4.6 Port Detail Content

When a port is selected, show:

```text
Port Name
Admin Status
Operational Status
Speed / Duplex
VLAN
Mode
Description
Connected MAC Count
CRC Errors
Input Errors
Discards
Last Change
Recent Events
Recent Diagnostic Runs
```

## 4.7 Detail Panel Rules

- Do not fully cover the main screen.
- Keep the selected table row or port tile visually connected to the panel.
- Use sections and dividers instead of heavy nested cards.
- Place dangerous or important actions at the bottom.
- Separate read-only actions from maintenance actions.
- Keep the panel scannable.
- Use fixed footer actions when necessary.

---

# 5. Command Preview Before Execution

## 5.1 Purpose

Diagnostic command execution must be safe and predictable.

Before running commands, the system must show a preview screen that clearly explains:

```text
Target device
Target IP
Target port
Diagnostic purpose
Command list
Command risk level
Expected output
Read-only status
Estimated execution time
Audit logging status
```

## 5.2 Required Execution Flow

```text
1. Select device
2. Select port or target
3. Select diagnostic purpose
4. System generates command plan
5. Show command preview
6. User confirms execution
7. Run diagnostic
8. Show parsed summary
9. Allow raw CLI review
10. Save diagnostic history and audit log
```

## 5.3 Preview Layout

```text
┌──────────────────────────────────────────────────────────────┐
│ Diagnostic Preview                                           │
├──────────────────────────────────────────────────────────────┤
│ Target Device : Core-SW-01                                   │
│ Management IP : 192.168.0.1                                  │
│ Target Port   : Gi1/0/24                                     │
│ Purpose       : Port error investigation                     │
│ Risk Level    : Read-only / Safe                             │
├──────────────────────────────────────────────────────────────┤
│ Commands to Run                                              │
│ 1. show interface Gi1/0/24                                    │
│ 2. show interface status                                      │
│ 3. show logging | include Gi1/0/24                            │
│ 4. show mac address-table interface Gi1/0/24                  │
├──────────────────────────────────────────────────────────────┤
│ Expected Output                                              │
│ - Interface status                                           │
│ - Error counters                                             │
│ - Recent log messages                                        │
│ - Connected MAC addresses                                    │
├──────────────────────────────────────────────────────────────┤
│ [Cancel]                                      [Run Diagnostic]│
└──────────────────────────────────────────────────────────────┘
```

## 5.4 Command Risk Levels

Every command must have one risk level.

```text
Read-only
Safe Diagnostic
Maintenance
Configuration Change
Blocked
```

Default system policy:

```text
Only Read-only and Safe Diagnostic commands are allowed in the normal diagnostic flow.
Configuration Change commands must not be exposed in the normal diagnostic screen.
Blocked commands must never be executable.
```

## 5.5 Preview Safety Rules

- The Run Diagnostic button is enabled only after preview is shown.
- The target device must be clearly visible.
- The target port must be clearly visible if applicable.
- The command list must be visible before execution.
- Empty command plans must not be executable.
- Unknown target devices must not be executable.
- Risky commands must disable the primary run button.
- Enter key must not accidentally execute commands.
- The user must understand that the diagnostic is read-only.

## 5.6 Recommended Safety Message

English UI:

```text
This diagnostic will run read-only commands only.
No configuration changes will be made.
```

Korean UI:

```text
이 진단은 조회 전용 명령만 실행합니다.
장비 설정은 변경되지 않습니다.
```

---

# 6. Alert Severity Badge System

## 6.1 Purpose

The severity badge system allows the operator to prioritize issues immediately.

The same severity system must be used across all screens.

## 6.2 Severity Levels

| Level | Label       | Meaning          |
| ----: | ----------- | ---------------- |
|     0 | Normal      | 정상             |
|     1 | Info        | 참고 정보        |
|     2 | Warning     | 주의 필요        |
|     3 | Critical    | 즉시 확인 필요   |
|     4 | Down        | 서비스 영향 가능 |
|     5 | Unknown     | 상태 확인 불가   |
|     6 | Maintenance | 점검 중          |
|     7 | Resolved    | 해결됨           |

## 6.3 Badge Requirements

Each badge must include:

```text
Color
Text label
Optional icon or dot
Tooltip explanation
Consistent meaning
```

Example:

```text
● Normal
● Warning
● Critical
● Down
● Unknown
● Maintenance
● Resolved
```

## 6.4 Color Direction

```text
Normal:         Muted Green
Info:           Muted Blue
Warning:        Amber
Critical:       Muted Red
Down:           Dark Red
Unknown:        Gray
Maintenance:    Blue Gray
Resolved:       Light Gray / Green Gray
```

## 6.5 Usage Locations

Use the same severity badge in:

```text
Dashboard
Device List
Port Matrix
Port Table
VLAN View
Diagnostic Result
Alert List
Maintenance History
Audit Log
Right Detail Panel
```

## 6.6 Default Sorting Priority

Sort abnormal states in this order:

```text
1. Down
2. Critical
3. Warning
4. Unknown
5. Maintenance
6. Info
7. Normal
8. Resolved
```

## 6.7 Recommended Technical Labels

Use short and meaningful labels.

Good examples:

```text
Down
CRC Error
High Error
STP Change
Link Flap
Unreachable
Auth Failed
Timeout
```

Avoid vague labels:

```text
Something went wrong
Issue detected
Abnormal status
Unknown problem
```

---

# 7. Raw CLI / Parsed Summary Split View

## 7.1 Purpose

Diagnostic results must be shown in two separate layers.

```text
Parsed Summary:
A structured and readable summary for fast decision-making.

Raw CLI:
The original command output for detailed technical verification.
```

The default view must show Parsed Summary first.
Raw CLI must be available but collapsed or separated in a tab.

## 7.2 Recommended Result Layout

```text
┌──────────────────────────────────────────────────────────────┐
│ Diagnostic Result                                            │
│ Device: Core-SW-01   Port: Gi1/0/24   Result: Warning        │
├──────────────────────────────────────────────────────────────┤
│ Parsed Summary                                               │
│ - Port is UP                                                 │
│ - CRC Errors detected: 12                                    │
│ - Last status change: 2 hours ago                            │
│ - Connected MAC count: 1                                     │
│ - Recommended next check: cable / endpoint NIC               │
├──────────────────────────────────────────────────────────────┤
│ Key Metrics                                                  │
│ Admin Status │ Oper Status │ Speed │ CRC │ Input Error │ MAC │
│ up           │ up          │ 1G    │ 12  │ 3           │ 1   │
├──────────────────────────────────────────────────────────────┤
│ Raw CLI Output                                               │
│ [Collapsed by default]                                       │
└──────────────────────────────────────────────────────────────┘
```

## 7.3 Parsed Summary Content

Parsed Summary must include:

```text
Final result status
Key abnormal findings
Normal findings
Comparison baseline if available
Possible cause
Recommended next check
Related port
Related VLAN
Related MAC address
Execution time
Executed by
```

## 7.4 Raw CLI Viewer Requirements

The Raw CLI Viewer must include:

```text
Monospace font
Proper line height
Copy button
Search within output
Expand / collapse
Command-level grouping
Error keyword highlight
Warning keyword highlight
Timestamp
Device name
Command name
Execution status
```

## 7.5 Raw CLI Example

```text
Command: show interface Gi1/0/24
Device : Core-SW-01
Time   : 2026-06-29 10:30:22
Status : Success

------------------------------------------------------------
GigabitEthernet1/0/24 is up, line protocol is up
  Hardware is Gigabit Ethernet
  Full-duplex, 1000Mb/s
  12 input errors, 12 CRC
------------------------------------------------------------
```

## 7.6 Recommended Result Tabs

```text
Summary
Metrics
Related Logs
Raw CLI
History
```

Default tab:

```text
Summary
```

## 7.7 Important Rules

- Do not mix summary and raw output in the same block.
- Do not show full raw CLI by default.
- Preserve raw CLI output.
- Allow copy of raw output.
- Highlight important error keywords.
- Show the command that produced each output.
- Mask sensitive data such as credentials, passwords, tokens, secrets, and SNMP community strings.

---

# 8. Integrated Practical Layout

## 8.1 Full Console Layout

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ Top Header                                                                 │
│ System Status | Last Sync | User | Session                                 │
├───────────────┬──────────────────────────────────────────────┬─────────────┤
│ Sidebar       │ Main Content                                  │ Detail Panel│
│               │                                               │             │
│ Dashboard     │ Device / Port / Diagnostic View               │ Summary     │
│ Devices       │                                               │ Health      │
│ Ports         │ Port Matrix                                   │ Diagnostics │
│ VLANs         │ Table / Logs                                  │ History     │
│ Diagnostics   │                                               │ Raw CLI     │
│ Alerts        │                                               │             │
│ History       │                                               │             │
└───────────────┴──────────────────────────────────────────────┴─────────────┘
```

## 8.2 Recommended Desktop Dimensions

```text
Sidebar:              220px to 240px
Top Header:           56px to 64px
Main Content Padding: 24px
Detail Panel:         420px
Table Row Height:     40px default
Compact Row Height:   32px to 36px
Port Tile:            44px x 36px or 52px x 40px
Badge Height:         22px to 24px
```

## 8.3 Density Modes

The system should support two density modes.

```text
Comfortable
Compact
```

Default mode:

```text
Comfortable
```

Recommended compact screens:

```text
Port Matrix
Device Table
Alert List
CLI Output
Maintenance History
```

---

# 9. Practical User Flows

## 9.1 Abnormal Port Investigation Flow

```text
Dashboard에서 Warning 확인
→ Device List에서 문제 장비 선택
→ Port Matrix에서 Error 포트 확인
→ 포트 클릭
→ 우측 상세 패널에서 CRC / Error 확인
→ Run Diagnostic 클릭
→ Command Preview 확인
→ 진단 실행
→ Parsed Summary 확인
→ 필요 시 Raw CLI 확인
→ Maintenance History에 기록
```

## 9.2 Device Health Check Flow

```text
Devices 메뉴 진입
→ Backbone 또는 L2 Switch 필터 선택
→ Status 기준 정렬
→ Unknown / Warning / Down 장비 우선 확인
→ 장비 클릭
→ 우측 패널에서 상태 확인
→ Diagnostic Preview 실행
→ Summary 및 Raw CLI 확인
```

## 9.3 MAC Address Lookup Flow

```text
MAC Lookup 진입
→ MAC 주소 입력
→ 관련 장비 / 포트 / VLAN 표시
→ 포트 클릭
→ 우측 패널에서 연결 상태 확인
→ 필요 시 진단 Preview 실행
```

---

# 10. Safety & Audit Rules

The UI must reduce operational mistakes.

Required safety rules:

```text
Always show target device before diagnostic execution.
Always show command list before diagnostic execution.
Always show risk level before diagnostic execution.
Do not execute commands without preview.
Do not expose configuration-changing commands in the default flow.
Do not show sensitive secrets in logs or errors.
Save diagnostic result history.
Save audit trail for command execution.
Show who executed the diagnostic.
Show when the diagnostic was executed.
```

---

# 11. Acceptance Criteria

The final UI must satisfy the following conditions:

```text
The operator can find Down or Critical devices quickly.
The operator can identify abnormal ports within 3 seconds on the port screen.
The operator can inspect device and port details without page switching.
The operator can preview commands before running diagnostics.
The operator can clearly distinguish Read-only commands from risky commands.
The operator can read parsed diagnostic results before opening raw CLI.
The operator can access raw CLI when technical verification is needed.
The operator can track diagnostic and maintenance history.
The system does not expose sensitive credentials or secrets.
The UI remains calm, professional, and suitable for hospital IT operations.
```

---

# 12. Final Design Principle

This system must not be designed as a simple admin dashboard.

It must be designed as a practical network operations console.

The final design must help the operator:

```text
See the problem
Understand the target
Preview the action
Run safe diagnostics
Review the summary
Verify raw evidence
Record the history
Avoid mistakes
```

The highest priorities are:

```text
Operational clarity
Safety
Fast troubleshooting
Consistent status representation
Readable network data
Minimal visual noise
```

```

```
