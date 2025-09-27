#!/usr/bin/env python3
"""
Interactive CLI for exploring mem-agent with sample memories.

The script auto-discovers memory packs under `./memories/` and lets you switch
between them before issuing queries. Scripted walkthroughs are currently geared
toward the `healthcare` pack, while other packs can be explored via custom
queries.

Prerequisites
-------------
1. Start the local model server: `make run-agent`
2. Expose the MCP endpoint: `make serve-mcp-http`
3. Ensure demo memories live under `./memories/`

Usage
-----
python examples/mem_agent_cli.py
# optional: python examples/mem_agent_cli.py --timeout 180
"""

from __future__ import annotations

import argparse
import copy
import json
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

import re

import requests
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# Paths & configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORIES_ROOT = REPO_ROOT / "memories"
MEMORY_PATH_FILE = REPO_ROOT / ".memory_path"

console = Console()

SAMPLE_PATIENTS = ["Sanjay Patel"]
TODAY = datetime.now().strftime("%Y-%m-%d")

SAMPLE_CLINICAL_NOTE = {
    "date": TODAY,
    "chief_complaint": "Diabetes follow-up and medication review",
    "subjective": (
        "Patient reports improved energy levels since last visit. Blood sugar "
        "readings have been more stable. No hypoglycemic episodes. Good "
        "adherence to medication regimen."
    ),
    "vitals": "BP 125/78 mmHg, HR 72 bpm, Weight 185 lbs (stable)",
    "physical_exam": "No acute distress. Feet examination shows no diabetic complications.",
    "assessment": "Type 2 diabetes well-controlled. Patient responding well to current regimen.",
    "plan": "Continue current medications. Recheck HbA1c in 3 months. Continue CGM monitoring.",
    "next_visit": "3 months for routine diabetes management",
}

SAMPLE_LAB_RESULTS = {
    "date": TODAY,
    "results": {
        "HbA1c": "6.7% (improved from 6.9%)",
        "Fasting Glucose": "118 mg/dL",
        "Creatinine": "0.9 mg/dL",
        "eGFR": ">90 mL/min/1.73m²",
        "LDL Cholesterol": "95 mg/dL",
    },
    "interpretation": (
        "Excellent diabetes control with HbA1c improvement. Kidney function remains normal. "
        "Lipid goals achieved."
    ),
}

SAMPLE_WEARABLE_DATA = {
    "date": TODAY,
    "device": "Apple Watch Series 8",
    "steps": "9,200 (above 8,500 average)",
    "active_minutes": "38 minutes of exercise",
    "distance": "4.2 miles",
    "sleep_hours": "7.2",
    "sleep_quality": "Good (82% efficiency)",
    "heart_rate": "Average 68 bpm, Max 145 bpm during exercise",
    "blood_pressure": "124/78 mmHg",
    "notes": "Patient maintaining excellent activity levels. No cardiac alerts.",
}

SAMPLE_APPOINTMENT_PROMPT = (
    "I have an appointment today. Prepare a pre-visit briefing covering medical status, recent "
    "changes, notable labs, red flags, and follow-up items."
)

SAMPLE_CARE_TEAM_PROMPT = (
    "Generate a care team coordination update highlighting recent developments, action items by "
    "provider role, patient education needs, scheduling recommendations, and coordination gaps."
)

SAMPLE_COHORT_PROMPT = (
    "Compare diabetes management across all Type 2 patients. Summarize HbA1c trends, medication "
    "effectiveness, lifestyle factors, and care coordination efficiency."
)

CLIENT_SUCCESS_PROMPTS = {
    "account_health": "What does the Client Health Check framework say about data sources and scoring for enterprise accounts?",
    "renewal_plan": "According to the Renewal Strategy Matrix, what timeline and guardrails apply to strategic account renewals like OrbitBank?",
    "escalation": "Describe the SEV-1 escalation steps and stakeholders from the escalation matrix.",
}

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def print_banner() -> None:
    title = Text("Mem-Agent Interactive CLI", style="bold white")
    subtitle = Text("Explore synthetic memories and guided workflows", style="italic dim")
    content = Text.assemble(title, "\n", subtitle)
    console.print(Panel.fit(content, border_style="green", padding=(1, 3)))


def print_section(title: str) -> None:
    console.print()
    console.print(Text(title, style="bold cyan"))


def format_block(text: str, indent: int = 2) -> str:
    wrapper = textwrap.TextWrapper(width=90, subsequent_indent=" " * indent)
    return wrapper.fill(textwrap.dedent(text).strip())


def display_response(title: str, response: str) -> None:
    body = format_block(response or "(no response returned)", indent=4)
    panel = Panel(body, title=title, border_style="cyan", padding=(1, 2))
    console.print(panel)


def input_with_default(prompt: str, default: str) -> str:
    value = console.input(f"[bold]{prompt}[/bold] [{default}]: ").strip()
    return value or default


def confirm(prompt: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    choice = console.input(f"[bold]{prompt}[/bold] ({suffix}): ").strip().lower()
    if not choice:
        return default
    return choice in {"y", "yes"}


def print_menu(options: List[tuple[str, str, Optional[Callable]]]) -> None:
    if not options:
        return
    table = Table(box=box.ROUNDED, highlight=True, padding=(0, 1))
    table.add_column("Key", style="bold yellow", justify="center")
    table.add_column("Action", style="white")
    for key, label, _ in options:
        table.add_row(key, label)
    console.print(table)


@dataclass
class UseCase:
    slug: str
    path: Path
    title: str
    description: str


def discover_use_cases() -> List[UseCase]:
    cases: List[UseCase] = []
    if not MEMORIES_ROOT.exists():
        return cases

    for directory in sorted(p for p in MEMORIES_ROOT.iterdir() if p.is_dir()):
        meta_file = directory / "meta.json"
        title = directory.name.replace("_", " ").title()
        description = "Sample memory pack"
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as fh:
                    meta = json.load(fh)
                title = meta.get("title", title)
                description = meta.get("description", description)
            except Exception:
                pass
        cases.append(UseCase(slug=directory.name, path=directory, title=title, description=description))
    return cases


def write_memory_path(path: Path) -> None:
    MEMORY_PATH_FILE.write_text(str(path.resolve()), encoding="utf-8")


def choose_use_case(preferred_slug: Optional[str] = None) -> UseCase:
    cases = discover_use_cases()
    if not cases:
        raise SystemExit("No memories found. Add folders under ./memories/ before running the CLI.")

    if preferred_slug:
        for case in cases:
            if case.slug == preferred_slug:
                write_memory_path(case.path)
                return case
        raise SystemExit(f"Use case '{preferred_slug}' not found. Available: {[c.slug for c in cases]}")

    print_section("Available Use Cases")
    for idx, case in enumerate(cases, start=1):
        console.print(f"[bold]{idx}[/bold] {case.title}\n    └─ {case.description}")

    while True:
        selection = console.input("Select a use case [1]: ").strip()
        if not selection:
            selection = "1"
        if selection.isdigit() and 1 <= int(selection) <= len(cases):
            chosen = cases[int(selection) - 1]
            write_memory_path(chosen.path)
            console.print(f"\n[green]Using memory directory:[/green] {chosen.path.resolve()}")
            return chosen
        console.print("[red]Please enter a valid number.[/red]")


def list_available_patients() -> List[str]:
    try:
        memory_dir = Path(MEMORY_PATH_FILE.read_text(encoding="utf-8").strip())
    except FileNotFoundError:
        return SAMPLE_PATIENTS

    user_file = memory_dir / "user.md"
    slug = memory_dir.name.lower()
    names: List[str] = []

    if user_file.exists():
        text = user_file.read_text(encoding="utf-8")
        pattern = re.compile(r"\[\[(.+?)(?:\|(.+?))?\]\]")
        for target, label in pattern.findall(text):
            display = label or Path(target).stem.replace("_", " ").title()
            target_lower = target.lower()
            if slug == "healthcare":
                if "patient" in target_lower:
                    names.append(display)
            else:
                names.append(display)

    if names:
        # preserve first occurrence order
        seen = set()
        ordered = []
        for name in names:
            if name not in seen:
                seen.add(name)
                ordered.append(name)
        return ordered

    # Fallback: scan markdown files under entities directories
    candidates: List[str] = []
    candidate_dirs = [memory_dir / "entities"]
    candidate_dirs.extend(p for p in memory_dir.glob("*/entities") if p.is_dir())

    for entities_dir in candidate_dirs:
        if not entities_dir.exists():
            continue
        for md_file in entities_dir.rglob("*.md"):
            rel = md_file.relative_to(memory_dir)
            rel_str = str(rel).lower()
            if slug == "healthcare" and "patient" not in rel_str:
                continue
            name = md_file.stem.replace("_", " ").title()
            candidates.append(name)

    if candidates:
        seen = set()
        ordered = []
        for name in candidates:
            if name not in seen:
                seen.add(name)
                ordered.append(name)
        return ordered

    return SAMPLE_PATIENTS


def prompt_patient() -> str:
    patients = list_available_patients()
    default = patients[0]
    console.print("\n[bold]Patients:[/bold]")
    for idx, name in enumerate(patients, start=1):
        console.print(f"  [cyan]{idx}[/cyan] {name}")
    choice = console.input("Select patient [1] or type a name: ").strip()
    if not choice:
        return default
    if choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= len(patients):
            return patients[idx - 1]
    return choice


def gather_clinical_note() -> Dict:
    if confirm("Use sample clinical note?", default=True):
        return copy.deepcopy(SAMPLE_CLINICAL_NOTE)

    note = {}
    note["date"] = input_with_default("Encounter date", SAMPLE_CLINICAL_NOTE["date"])
    note["chief_complaint"] = input_with_default("Chief complaint", SAMPLE_CLINICAL_NOTE["chief_complaint"])
    note["subjective"] = input_with_default("Subjective", SAMPLE_CLINICAL_NOTE["subjective"])
    note["vitals"] = input_with_default("Vitals", SAMPLE_CLINICAL_NOTE["vitals"])
    note["physical_exam"] = input_with_default("Physical exam", SAMPLE_CLINICAL_NOTE["physical_exam"])
    note["assessment"] = input_with_default("Assessment", SAMPLE_CLINICAL_NOTE["assessment"])
    note["plan"] = input_with_default("Plan", SAMPLE_CLINICAL_NOTE["plan"])
    note["next_visit"] = input_with_default("Next visit plan", SAMPLE_CLINICAL_NOTE["next_visit"])
    return note


def gather_lab_results() -> Dict:
    if confirm("Use sample lab panel?", default=True):
        return copy.deepcopy(SAMPLE_LAB_RESULTS)

    lab_data: Dict[str, Dict] = {
        "date": input_with_default("Lab date", SAMPLE_LAB_RESULTS["date"]),
        "results": {},
    }
    console.print("Enter lab results as 'Test: value'. Leave blank to finish.")
    while True:
        line = console.input("  Result: ").strip()
        if not line:
            break
        if ":" in line:
            test, value = (part.strip() for part in line.split(":", 1))
        else:
            test = f"Result {len(lab_data['results']) + 1}"
            value = line
        lab_data["results"][test] = value
    lab_data["interpretation"] = input_with_default(
        "Interpretation", SAMPLE_LAB_RESULTS.get("interpretation", "")
    )
    return lab_data


def gather_wearable_data() -> Dict:
    if confirm("Use sample wearable summary?", default=True):
        return copy.deepcopy(SAMPLE_WEARABLE_DATA)

    data = {}
    for key, prompt in [
        ("date", "Summary date"),
        ("device", "Device"),
        ("steps", "Steps"),
        ("active_minutes", "Active minutes"),
        ("distance", "Distance"),
        ("sleep_hours", "Sleep hours"),
        ("sleep_quality", "Sleep quality"),
        ("heart_rate", "Heart rate"),
        ("blood_pressure", "Blood pressure"),
        ("notes", "Notes"),
    ]:
        data[key] = input_with_default(prompt, SAMPLE_WEARABLE_DATA.get(key, ""))
    return data

# ---------------------------------------------------------------------------
# Mem-agent client
# ---------------------------------------------------------------------------


class MemAgentClient:
    """HTTP client for interacting with mem-agent workflows."""

    def __init__(self, base_url: str = "http://localhost:8081", request_timeout: float = 240.0):
        self.base_url = base_url
        self.mcp_endpoint = f"{base_url}/mcp"
        self.request_timeout = request_timeout

    def _call(self, payload: Dict) -> str:
        try:
            response = requests.post(
                self.mcp_endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.request_timeout,
            )
        except requests.RequestException as exc:
            return f"Connection error: {exc}"

        if response.status_code != 200:
            return f"HTTP {response.status_code}: {response.text}"

        try:
            parsed = response.json()
        except ValueError as exc:
            return f"Invalid JSON response: {exc}"

        result = parsed.get("result")
        if not result:
            return f"Unexpected response: {parsed}"

        content = result.get("content", [])
        if isinstance(content, list) and content:
            return content[0].get("text", "") or "Empty response"
        if isinstance(content, str):
            return content
        return "No textual content returned"

    def query_memory(self, question: str) -> str:
        console.print(Panel(question.strip() or "(empty prompt)", title="Prompt", border_style="magenta", padding=(1, 2)))
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "use_memory_agent",
                "arguments": {"question": question},
            },
        }
        return self._call(payload)

    def get_patient_overview(self, patient_name: str) -> str:
        prompt = f"""
        Provide a comprehensive overview of {patient_name} including:
        - Current medical conditions and medications
        - Recent clinical encounters and changes
        - Key risk factors and assessments
        - Care team and coordination status
        """
        return self.query_memory(prompt)

    def add_clinical_note(self, patient_name: str, clinical_data: Dict) -> str:
        prompt = f"""
        Please add this clinical encounter to {patient_name}'s memory:

        CLINICAL NOTE - {clinical_data.get('date', TODAY)}
        Patient: {patient_name}
        Chief Complaint: {clinical_data.get('chief_complaint', 'Routine follow-up')}

        Subjective: {clinical_data.get('subjective', '')}

        Objective:
        - Vital Signs: {clinical_data.get('vitals', '')}
        - Physical Exam: {clinical_data.get('physical_exam', '')}

        Assessment: {clinical_data.get('assessment', '')}

        Plan: {clinical_data.get('plan', '')}

        Next Visit: {clinical_data.get('next_visit', 'As needed')}
        """
        return self.query_memory(prompt)

    def add_lab_results(self, patient_name: str, lab_data: Dict) -> str:
        prompt = f"""
        Please add these lab results to {patient_name}'s memory:

        LAB RESULTS - {lab_data.get('date', TODAY)}
        Patient: {patient_name}

        Results:
        """
        for test, value in lab_data.get("results", {}).items():
            prompt += f"- {test}: {value}\n"
        interpretation = lab_data.get("interpretation")
        if interpretation:
            prompt += f"\nInterpretation: {interpretation}"
        return self.query_memory(prompt)

    def add_wearable_data(self, patient_name: str, wearable_data: Dict) -> str:
        prompt = f"""
        Please add this wearable device data to {patient_name}'s memory:

        WEARABLE DATA SUMMARY - {wearable_data.get('date', TODAY)}
        Patient: {patient_name}
        Device: {wearable_data.get('device', 'Fitness Tracker')}

        Activity:
        - Steps: {wearable_data.get('steps', 'N/A')}
        - Active Minutes: {wearable_data.get('active_minutes', 'N/A')}
        - Distance: {wearable_data.get('distance', 'N/A')}

        Sleep:
        - Total Sleep: {wearable_data.get('sleep_hours', 'N/A')} hours
        - Sleep Quality: {wearable_data.get('sleep_quality', 'N/A')}

        Vitals:
        - Heart Rate: {wearable_data.get('heart_rate', 'N/A')}
        - Blood Pressure: {wearable_data.get('blood_pressure', 'N/A')}

        Notes: {wearable_data.get('notes', '')}
        """
        return self.query_memory(prompt)

    def prepare_appointment_context(self, patient_name: str, extra_prompt: str) -> str:
        prompt = f"""
        I have an appointment with {patient_name} today. {extra_prompt}
        """
        return self.query_memory(prompt)

    def generate_care_team_update(self, patient_name: str, extra_prompt: str) -> str:
        prompt = f"""
        Generate a care team update for {patient_name}. {extra_prompt}
        """
        return self.query_memory(prompt)

# ---------------------------------------------------------------------------
# CLI actions
# ---------------------------------------------------------------------------


def action_connection_test(agent: MemAgentClient) -> None:
    response = agent.query_memory("Are you connected and ready to help with patient memory?")
    display_response("Connection Check", response)


def action_patient_overview(agent: MemAgentClient) -> None:
    patient = prompt_patient()
    response = agent.get_patient_overview(patient)
    display_response(f"Overview for {patient}", response)


def action_add_clinical_note(agent: MemAgentClient) -> None:
    patient = prompt_patient()
    data = gather_clinical_note()
    response = agent.add_clinical_note(patient, data)
    display_response("Clinical Note Response", response)


def action_add_lab_results(agent: MemAgentClient) -> None:
    patient = prompt_patient()
    data = gather_lab_results()
    response = agent.add_lab_results(patient, data)
    display_response("Lab Results Response", response)


def action_add_wearable_data(agent: MemAgentClient) -> None:
    patient = prompt_patient()
    data = gather_wearable_data()
    response = agent.add_wearable_data(patient, data)
    display_response("Wearable Data Response", response)


def action_prepare_appointment(agent: MemAgentClient) -> None:
    patient = prompt_patient()
    extra = input_with_default("Additional instructions", SAMPLE_APPOINTMENT_PROMPT)
    response = agent.prepare_appointment_context(patient, extra)
    display_response("Pre-Visit Briefing", response)


def action_care_team_update(agent: MemAgentClient) -> None:
    patient = prompt_patient()
    extra = input_with_default("Additional instructions", SAMPLE_CARE_TEAM_PROMPT)
    response = agent.generate_care_team_update(patient, extra)
    display_response("Care Team Update", response)


def action_cohort_analysis(agent: MemAgentClient) -> None:
    prompt = input_with_default("Cohort analysis prompt", SAMPLE_COHORT_PROMPT)
    response = agent.query_memory(prompt)
    display_response("Population Insights", response)


def action_custom_query(agent: MemAgentClient) -> None:
    question = console.input("Enter your question: ").strip()
    if not question:
        console.print("[yellow]No question provided.[/yellow]")
        return
    response = agent.query_memory(question)
    display_response("Custom Query", response)


def action_add_data(agent: MemAgentClient) -> None:
    data_actions: List[tuple[str, str, Optional[Callable]]] = [
        ("1", "Add clinical note", action_add_clinical_note),
        ("2", "Add lab results", action_add_lab_results),
        ("3", "Add wearable data", action_add_wearable_data),
        ("b", "Back", None),
    ]

    while True:
        print_section("Add Patient Data")
        print_menu(data_actions)
        choice = console.input("Select data action: ").strip().lower()
        if choice in {"b", "", "q"}:
            return

        handler = next((h for key, _, h in data_actions if key == choice), None)
        if not handler:
            console.print("[red]Unknown option. Please try again.[/red]")
            continue
        handler(agent)


def action_guided_walkthrough(agent: MemAgentClient) -> None:
    patient = prompt_patient()
    print_section("Guided Scenario")
    console.print("Running end-to-end workflow. This may take a minute...\n", style="dim")

    display_response(
        "Connection Check",
        agent.query_memory("Are you connected and ready to help with patient memory?"),
    )
    display_response(
        f"Overview for {patient}",
        agent.get_patient_overview(patient),
    )
    display_response(
        "Clinical Note Response",
        agent.add_clinical_note(patient, copy.deepcopy(SAMPLE_CLINICAL_NOTE)),
    )
    display_response(
        "Lab Results Response",
        agent.add_lab_results(patient, copy.deepcopy(SAMPLE_LAB_RESULTS)),
    )
    display_response(
        "Wearable Data Response",
        agent.add_wearable_data(patient, copy.deepcopy(SAMPLE_WEARABLE_DATA)),
    )
    display_response(
        "Pre-Visit Briefing",
        agent.prepare_appointment_context(patient, SAMPLE_APPOINTMENT_PROMPT),
    )
    display_response(
        "Care Team Update",
        agent.generate_care_team_update(patient, SAMPLE_CARE_TEAM_PROMPT),
    )
    display_response(
        "Population Insights",
        agent.query_memory(SAMPLE_COHORT_PROMPT),
    )

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_cli(args: argparse.Namespace) -> None:
    print_banner()
    chosen = choose_use_case(preferred_slug=args.use_case)
    if chosen.slug != "healthcare":
        console.print(
            "\n[dim]Scripted actions are tailored for the 'healthcare' pack. Custom queries remain available for other memories.[/dim]"
        )

    agent = MemAgentClient(base_url=args.base_url, request_timeout=args.timeout)
    actions: List[tuple[str, str, Optional[Callable]]] = []
    actions.append(("1", "Connection check", action_connection_test))

    next_key = 2
    if chosen.slug == "healthcare":
        actions.append((str(next_key), "Guided walkthrough", action_guided_walkthrough))
        next_key += 1
        actions.append((str(next_key), "Patient overview", action_patient_overview))
        next_key += 1
        actions.append((str(next_key), "Add patient data", action_add_data))
        next_key += 1
    elif chosen.slug == "client_success":
        def action_client_health(agent: MemAgentClient) -> None:
            display_response(
                "Account Health",
                agent.query_memory(CLIENT_SUCCESS_PROMPTS["account_health"]),
            )

        def action_client_renewal(agent: MemAgentClient) -> None:
            display_response(
                "Renewal Plan",
                agent.query_memory(CLIENT_SUCCESS_PROMPTS["renewal_plan"]),
            )

        def action_client_escalation(agent: MemAgentClient) -> None:
            display_response(
                "Escalation Process",
                agent.query_memory(CLIENT_SUCCESS_PROMPTS["escalation"]),
            )

        actions.append((str(next_key), "Account health summary", action_client_health))
        next_key += 1
        actions.append((str(next_key), "OrbitBank renewal plan", action_client_renewal))
        next_key += 1
        actions.append((str(next_key), "Escalation process", action_client_escalation))
        next_key += 1
    else:
        console.print("\n[dim]Tip: switch back to 'healthcare' for guided demos.[/dim]")

    actions.append((str(next_key), "Custom query", action_custom_query))
    actions.append(("q", "Quit", None))

    action_map = {key: handler for key, _, handler in actions}

    while True:
        print_menu(actions)
        choice = console.input("[bold]Select an action (q to quit): [/bold]").strip().lower()
        if not choice:
            continue
        if choice == "0":
            choice = "q"
        if choice == "q":
            console.print("\n[green]Goodbye![/green]")
            break
        handler = action_map.get(choice)
        if not handler:
            console.print("[red]Unknown option. Please try again.[/red]")
            continue
        handler(agent)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Explore mem-agent healthcare memories via CLI")
    parser.add_argument("--base-url", default="http://localhost:8081", help="Base URL for the MCP server")
    parser.add_argument("--timeout", type=float, default=240.0, help="Request timeout in seconds")
    parser.add_argument("--use-case", help="Slug of the memory pack to load (defaults to interactive prompt)")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    try:
        run_cli(args)
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted by user.[/dim]")


if __name__ == "__main__":
    main()
