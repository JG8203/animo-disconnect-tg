from typing import List, Dict, Any

def format_section(section: Dict[str, Any]) -> str:
    """Return a human-readable Markdown description of one section."""
    meetings = [
        f"{m.get('day', '')} {m.get('time', '')} {m.get('room') or 'Online'}"
        for m in section.get("meetings", [])
    ]
    meetings_str = (
        " | ".join(m.strip() for m in meetings if m.strip())
        or "No schedule information"
    )

    return (
        f"*{section.get('course', 'N/A')} {section.get('section', 'N/A')}* "
        f"(Class {section.get('classNbr', 'N/A')})\n"
        f"Enrolled: {section.get('enrolled', '?')}/{section.get('enrlCap', '?')} "
        f"| {section.get('remarks', '')}\n"
        f"Instructor: {section.get('instructor', 'TBA')}\n"
        f"Schedule: {meetings_str}\n"
    )

def compose_status_lines(
    course: str,
    sections: List[Dict[str, Any]],
    title_suffix: str = "",
) -> List[str]:
    """Build a list of markdown strings representing the status of sections."""
    sections = sorted(sections, key=lambda s: s.get("section", ""))
    open_sections = [s for s in sections if s.get("enrolled", 0) < s.get("enrlCap", 0)]
    full_sections = [s for s in sections if s.get("enrolled", 0) >= s.get("enrlCap", 0)]

    lines: List[str] = [
        f"*{course}{title_suffix}*",
        f"Total: {len(sections)} | "
        f"Open: {len(open_sections)} | Full: {len(full_sections)}",
        "",
    ]

    if open_sections:
        lines.append("*Open sections*")
        lines.extend(format_section(s) for s in open_sections)
        lines.append("")

    if full_sections:
        lines.append("*Full sections*")
        lines.extend(format_section(s) for s in full_sections)

    return lines

def diff_courses(old: List[Dict[str, Any]], new: List[Dict[str, Any]]) -> Dict[str, List]:
    """Compute differences between course sections."""
    old_by_number = {s["classNbr"]: s for s in old if "classNbr" in s}
    new_by_number = {s["classNbr"]: s for s in new if "classNbr" in s}

    added = [s for k, s in new_by_number.items() if k not in old_by_number]
    removed = [s for k, s in old_by_number.items() if k not in new_by_number]

    enrollment_changes: List[Dict[str, Any]] = []
    for class_number, new_section in new_by_number.items():
        if class_number in old_by_number:
            old_enrolled = old_by_number[class_number].get("enrolled")
            new_enrolled = new_section.get("enrolled")
            if (
                isinstance(old_enrolled, int)
                and isinstance(new_enrolled, int)
                and old_enrolled != new_enrolled
            ):
                enrollment_changes.append({
                    "section": new_section,
                    "old_enrolled": old_enrolled,
                    "new_enrolled": new_enrolled,
                })

    return {"added": added, "removed": removed, "enrollment": enrollment_changes}

def compose_update_lines(course: str, changes: Dict[str, List], title_suffix: str = "") -> List[str]:
    """Build a list of markdown strings describing course updates."""
    lines = [f"*Updates for {course}{title_suffix}* 📢"]

    if changes["added"]:
        lines.append("\n*🆕 New sections added*")
        lines.extend(format_section(s) for s in changes["added"])

    if changes["removed"]:
        lines.append("\n*🗑️ Sections removed*")
        lines.extend(format_section(s) for s in changes["removed"])

    if changes["enrollment"]:
        lines.append("\n*📊 Enrollment changes*")
        sorted_changes = sorted(
            changes["enrollment"],
            key=lambda c: (c["section"].get("course", ""), c["section"].get("section", "")),
        )
        for change in sorted_changes:
            section = change["section"]
            old_enrl = change["old_enrolled"]
            new_enrl = change["new_enrolled"]
            cap = section.get("enrlCap", "?")
            delta = new_enrl - old_enrl
            emoji = "📈" if delta > 0 else "📉"
            lines.append(
                f"{emoji} {section.get('course','?')} {section.get('section','?')} "
                f"(Class {section.get('classNbr','?')}) "
                f"`{old_enrl} ➡️ {new_enrl}` / {cap}"
            )

    return lines

