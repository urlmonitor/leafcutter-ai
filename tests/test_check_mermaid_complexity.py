"""Tests for scripts/commit_guardian/check_mermaid_complexity.py."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "commit_guardian"))

from check_mermaid_complexity import (
    check_file,
    count_elements,
    detect_diagram_type,
    extract_mermaid_blocks,
)


class TestDetectDiagramType:
    def test_flowchart(self):
        assert detect_diagram_type(["flowchart LR"]) == "flowchart"

    def test_graph(self):
        assert detect_diagram_type(["graph TD"]) == "flowchart"

    def test_c4_context(self):
        assert detect_diagram_type(["C4Context"]) == "c4"

    def test_c4_container(self):
        assert detect_diagram_type(["C4Container"]) == "c4"

    def test_sequence(self):
        assert detect_diagram_type(["sequenceDiagram"]) == "sequence"

    def test_erd(self):
        assert detect_diagram_type(["erDiagram"]) == "erd"

    def test_state(self):
        assert detect_diagram_type(["stateDiagram-v2"]) == "state"

    def test_class_diagram(self):
        assert detect_diagram_type(["classDiagram"]) == "class"

    def test_unknown(self):
        assert detect_diagram_type(["pie"]) is None

    def test_skips_empty_lines(self):
        assert detect_diagram_type(["", "  ", "sequenceDiagram"]) == "sequence"


class TestExtractMermaidBlocks:
    def test_single_block(self):
        content = "# Title\n\n```mermaid\nflowchart LR\n  A --> B\n```\n\nDone."
        blocks = extract_mermaid_blocks(content)
        assert len(blocks) == 1
        assert blocks[0][0] == 1
        assert "flowchart LR" in blocks[0][1]

    def test_multiple_blocks(self):
        content = "```mermaid\nflowchart LR\n  A-->B\n```\n\n```mermaid\nerDiagram\n  T {\n  int id\n  }\n```\n"
        blocks = extract_mermaid_blocks(content)
        assert len(blocks) == 2

    def test_no_blocks(self):
        content = "# Just markdown\n\nNo diagrams here.\n"
        blocks = extract_mermaid_blocks(content)
        assert len(blocks) == 0


class TestCountElements:
    def test_flowchart_nodes_and_edges(self):
        lines = [
            "flowchart LR",
            "  A[Source]",
            "  B[Transform]",
            "  C[Sink]",
            "  A --> B",
            "  B --> C",
        ]
        counts = count_elements(lines, "flowchart")
        assert counts["nodes"] == 3
        assert counts["edges"] == 2

    def test_c4_nodes_and_edges(self):
        lines = [
            "C4Context",
            '    Person(user, "User", "")',
            '    System(sys, "System", "")',
            '    System_Ext(ext, "External", "")',
            '    Rel(user, sys, "Uses")',
            '    Rel(sys, ext, "Calls")',
        ]
        counts = count_elements(lines, "c4")
        assert counts["nodes"] == 3
        assert counts["edges"] == 2

    def test_sequence_participants_and_interactions(self):
        lines = [
            "sequenceDiagram",
            "    participant A as Alice",
            "    participant B as Bob",
            "    participant C as Carol",
            "    A->>B: hello",
            "    B-->>A: hi",
            "    A->>C: hey",
        ]
        counts = count_elements(lines, "sequence")
        assert counts["participants"] == 3
        assert counts["interactions"] == 3

    def test_erd_tables(self):
        lines = [
            "erDiagram",
            "    USERS {",
            "        int id PK",
            "        text name",
            "    }",
            "    ORDERS {",
            "        int id PK",
            "    }",
        ]
        counts = count_elements(lines, "erd")
        assert counts["tables"] == 2

    def test_state_states(self):
        lines = [
            "stateDiagram-v2",
            "    [*] --> Idle",
            "    Idle : waiting",
            "    Processing : working",
            "    state Fork <<fork>>",
        ]
        counts = count_elements(lines, "state")
        assert counts["states"] >= 3

    def test_class_classes(self):
        lines = [
            "classDiagram",
            "    class Animal {",
            "        +name: str",
            "    }",
            "    class Dog {",
            "        +bark()",
            "    }",
        ]
        counts = count_elements(lines, "class")
        assert counts["classes"] == 2

    def test_boundaries(self):
        lines = [
            "C4Container",
            '    System_Boundary(b1, "Boundary1") {',
            '        Container(a, "A", "", "")',
            "    }",
            "    subgraph External",
            '        Container(b, "B", "", "")',
            "    end",
        ]
        counts = count_elements(lines, "c4")
        assert counts["boundaries"] == 2


class TestCheckFile:
    def test_clean_file_returns_no_warnings(self, tmp_path):
        md = tmp_path / "clean.md"
        md.write_text("# Doc\n\n```mermaid\nflowchart LR\n  A[One] --> B[Two]\n```\n")
        assert check_file(str(md)) == []

    def test_exceeds_node_threshold(self, tmp_path):
        nodes = "\n".join(f"  N{i}[Node{i}]" for i in range(20))
        md = tmp_path / "complex.md"
        md.write_text(f"# Doc\n\n```mermaid\nflowchart LR\n{nodes}\n```\n")
        warnings = check_file(str(md))
        assert len(warnings) >= 1
        assert "nodes" in warnings[0]

    def test_exceeds_participant_threshold(self, tmp_path):
        participants = "\n".join(f"    participant P{i} as Person{i}" for i in range(10))
        md = tmp_path / "seq.md"
        md.write_text(f"# Doc\n\n```mermaid\nsequenceDiagram\n{participants}\n```\n")
        warnings = check_file(str(md))
        assert len(warnings) >= 1
        assert "participants" in warnings[0]

    def test_exceeds_boundary_threshold(self, tmp_path):
        boundaries = "\n".join(f'    System_Boundary(b{i}, "B{i}") {{' for i in range(6))
        md = tmp_path / "bound.md"
        md.write_text(f"# Doc\n\n```mermaid\nC4Container\n{boundaries}\n```\n")
        warnings = check_file(str(md))
        assert len(warnings) >= 1
        assert "boundaries" in warnings[0]

    def test_bypass_token_skips(self, tmp_path):
        nodes = "\n".join(f"  N{i}[Node{i}]" for i in range(20))
        md = tmp_path / "bypass.md"
        md.write_text(f"# Doc\n\n```mermaid\nflowchart LR\n{nodes}\n```\n")

        with patch(
            "check_mermaid_complexity.get_staged_md_files",
            return_value=[str(md)],
        ), patch(
            "check_mermaid_complexity.get_commit_message",
            return_value="feat: add diagram [NO-COMPLEXITY-CHECK]",
        ):
            from check_mermaid_complexity import main
            result = main()
            assert result == 0
