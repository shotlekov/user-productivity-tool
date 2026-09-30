import tempfile
import unittest
from pathlib import Path

import user_productivity_tool as tool


SAMPLE_CSV = """day,hour,username,action
2026-09-24,09:00,Alice,Ingest clip
2026-09-24,09:03,Alice,Custom QA
2026-09-24,09:06,Bob,Edit clip
"""

RAW_SEMICOLON_CSV = """day;hour;username;action;"sub action";"clip ID";iBot
16.09.2026;00:00:13;metodi.shotlekov;Login;;;
16.09.2026;00:00:44;system;"Add detect";;50905473;Y
16.09.2026;00:01:13;metodi.shotlekov;"Ingest clip";;50905474;N
"""


class UserProductivityGuiTests(unittest.TestCase):
    def test_main_without_args_opens_gui_runner(self):
        calls = []

        exit_code = tool.main([], gui_runner=lambda: calls.append("opened"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(calls, ["opened"])

    def test_discover_actions_for_gui_combines_default_and_csv_actions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "actions.csv"
            csv_path.write_text(SAMPLE_CSV, encoding="utf-8")

            actions, weights = tool.discover_actions_for_gui(csv_path)

        self.assertEqual(
            actions,
            [
                "Ingest clip",
                "Edit clip",
                "Update detect",
                "Deactivate clip & delete detects",
                "Mark POI as Done",
                "Custom QA",
            ],
        )
        self.assertEqual(weights["Ingest clip"], 5.0)
        self.assertEqual(weights["Custom QA"], 1.0)

    def test_discover_users_for_gui_reads_non_system_csv_users(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "actions.csv"
            csv_path.write_text(SAMPLE_CSV + "2026-09-24,09:09,system,Edit clip\n", encoding="utf-8")

            users = tool.discover_users_for_gui(csv_path)

        self.assertEqual(users, ["Alice", "Bob"])

    def test_build_report_filters_selected_users_from_all_calculations(self):
        csv_text = """day,hour,username,action
2026-09-24,09:00,Alice,Ingest clip
2026-09-24,09:01,Alice,Edit clip
2026-09-24,10:00,Bob,Ingest clip
2026-09-24,10:10,Bob,Edit clip
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "actions.csv"
            csv_path.write_text(csv_text, encoding="utf-8")

            report = tool.build_user_productivity_report(
                csv_path,
                threshold_minutes=20,
                selected_actions=["Ingest clip", "Edit clip"],
                selected_users=["Alice"],
            )

        self.assertEqual(report["users"], ["Alice"])
        self.assertEqual(report["selected_users"], ["Alice"])
        self.assertEqual(report["source_rows"], 2)
        self.assertEqual([row["username"] for row in report["ranking"]], ["Alice"])
        self.assertEqual(report["volume_reference"]["total_volume"], 2)

    def test_cli_accepts_user_filter_for_markdown_export(self):
        csv_text = """day,hour,username,action
2026-09-24,09:00,Alice,Ingest clip
2026-09-24,09:01,Alice,Edit clip
2026-09-24,10:00,Bob,Ingest clip
2026-09-24,10:10,Bob,Edit clip
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "actions.csv"
            output_path = Path(tmpdir) / "report.md"
            csv_path.write_text(csv_text, encoding="utf-8")

            exit_code = tool.main([
                "--input",
                str(csv_path),
                "--output",
                str(output_path),
                "--threshold-minutes",
                "20",
                "--user",
                "Alice",
            ])

            markdown = output_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("| 1 | Alice |", markdown)
        self.assertNotIn("| 1 | Bob |", markdown)

    def test_read_action_log_csv_accepts_raw_semicolon_export_and_skips_system(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "raw_actions.csv"
            csv_path.write_text(RAW_SEMICOLON_CSV, encoding="utf-8")

            rows = tool.read_action_log_csv(csv_path)

        self.assertEqual([row["username"] for row in rows], ["metodi.shotlekov", "metodi.shotlekov"])
        self.assertEqual([row["action"] for row in rows], ["Login", "Ingest clip"])
        self.assertEqual(rows[0]["dt"].strftime("%Y-%m-%d %H:%M:%S"), "2026-09-16 00:00:13")

    def test_result_value_tags_classify_against_median(self):
        values = [50.0, 100.0, 150.0]

        self.assertEqual(tool._median_numeric(values), 100.0)
        self.assertEqual(tool._value_result_tag(150.0, 100.0), "above_median")
        self.assertEqual(tool._value_result_tag(50.0, 100.0), "below_median")
        self.assertEqual(tool._value_result_tag(100.0, 100.0), "near_median")
        self.assertEqual(tool._value_result_tag(50.0, 100.0, lower_is_better=True), "above_median")

    def test_sort_ranking_rows_supports_metrics_and_duration(self):
        rows = [
            {"display_name": "Slow", "total_volume": 10, "score": 50.0, "speed_factor": 0.8, "avg_duration": "02:00.000"},
            {"display_name": "Fast", "total_volume": 5, "score": 80.0, "speed_factor": 1.4, "avg_duration": "00:30.000"},
            {"display_name": "Busy", "total_volume": 20, "score": 60.0, "speed_factor": 1.0, "avg_duration": "01:00.000"},
        ]

        self.assertEqual([row["display_name"] for row in tool._sort_ranking_rows(rows, "total_actions", descending=True)], ["Busy", "Slow", "Fast"])
        self.assertEqual([row["display_name"] for row in tool._sort_ranking_rows(rows, "score", descending=True)], ["Fast", "Busy", "Slow"])
        self.assertEqual([row["display_name"] for row in tool._sort_ranking_rows(rows, "avg_duration", descending=False)], ["Fast", "Busy", "Slow"])


if __name__ == "__main__":
    unittest.main()
