# Changelog

## 1.2.0 - 2026-04-21

### UI Changes
- Set the default accent color to `#A923E2`.
- Reworked the Home overlay control into one stateful button:
  - `Deactivate` in gray while overlay is active.
  - `Activate` in accent color while overlay is inactive.
- Improved Crosshairs page structure with cleaner row layout for controls and content.
- Improved rounded corner rendering for preview surfaces and scroll sections.

### Bug Fixes
- Fixed UI text clipping and overflow issues in Crosshairs and Detail views by adding scroll-safe layouts.
- Fixed folder/button restyling refresh issues when switching filters.
- Fixed favorite heart symbol rendering issues by using stable unicode escape sequences.
