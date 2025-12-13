"""Tests for output formatters."""
import pytest
import json
from pathlib import Path
from src.formatters import JsonFormatter, CsvFormatter, MarkdownFormatter, get_formatter
from src.models import ModInfo, ScanResult


@pytest.fixture
def sample_scan_result():
    """Create a sample scan result for testing."""
    mods = [
        ModInfo(
            name="Test Mod 1",
            loader="fabric",
            version="1.0.0",
            filename="test1.jar",
            mod_id="test_mod_1",
            dependencies=["fabricloader", "minecraft"],
            author="Author1",
            description="Test description 1",
            mc_versions=["1.20.1"],
            disabled=False,
        ),
        ModInfo(
            name="Test Mod 2",
            loader="forge",
            version="2.0.0",
            filename="test2.jar",
            mod_id="test_mod_2",
            dependencies=["forge"],
            author="Author2",
            description="Test description 2",
            mc_versions=["1.19.2", "1.20.1"],
            disabled=False,
        ),
    ]

    return ScanResult(mods=mods, total_files=2, scan_duration=1.5, errors=[])


class TestJsonFormatter:
    """Tests for JSON formatter."""

    def test_format_output(self, sample_scan_result):
        """Test JSON formatting."""
        formatter = JsonFormatter()
        output = formatter.format(sample_scan_result)

        # Should be valid JSON
        data = json.loads(output)
        assert data["total_mods"] == 2
        assert len(data["mods"]) == 2
        assert data["mods"][0]["name"] == "Test Mod 1"

    def test_format_compact(self, sample_scan_result):
        """Test compact JSON formatting."""
        formatter = JsonFormatter()
        output = formatter.format(sample_scan_result, compact=True)

        # Compact should have no indentation
        assert "\n" not in output or "  " not in output

    def test_save_to_file(self, sample_scan_result, temp_dir):
        """Test saving JSON to file."""
        formatter = JsonFormatter()
        output_path = temp_dir / "output.json"

        formatter.save(sample_scan_result, output_path)

        assert output_path.exists()

        # Verify content
        with open(output_path) as f:
            data = json.load(f)
        assert data["total_mods"] == 2


class TestCsvFormatter:
    """Tests for CSV formatter."""

    def test_format_output(self, sample_scan_result):
        """Test CSV formatting."""
        formatter = CsvFormatter()
        output = formatter.format(sample_scan_result)

        lines = output.strip().split("\n")

        # Should have header + 2 data rows
        assert len(lines) == 3
        assert "Name" in lines[0]
        assert "Test Mod 1" in lines[1]
        assert "Test Mod 2" in lines[2]

    def test_save_to_file(self, sample_scan_result, temp_dir):
        """Test saving CSV to file."""
        formatter = CsvFormatter()
        output_path = temp_dir / "output.csv"

        formatter.save(sample_scan_result, output_path)

        assert output_path.exists()


class TestMarkdownFormatter:
    """Tests for Markdown formatter."""

    def test_format_output(self, sample_scan_result):
        """Test Markdown formatting."""
        formatter = MarkdownFormatter()
        output = formatter.format(sample_scan_result)

        # Should contain markdown table syntax
        assert "##" in output  # Headers
        assert "|" in output  # Table borders
        assert "Test Mod 1" in output
        assert "Test Mod 2" in output

    def test_format_detailed(self, sample_scan_result):
        """Test detailed Markdown formatting."""
        formatter = MarkdownFormatter()
        output = formatter.format(sample_scan_result, detailed=True)

        # Detailed should include mod info
        assert "Test Mod 1" in output
        assert "fabricloader" in output or "fabric" in output.lower()


class TestFormatterRegistry:
    """Tests for formatter registry and lookup."""

    def test_get_formatter_by_name(self):
        """Test getting formatter by name."""
        formatter = get_formatter("json")
        assert isinstance(formatter, JsonFormatter)

        formatter = get_formatter("csv")
        assert isinstance(formatter, CsvFormatter)

        formatter = get_formatter("markdown")
        assert isinstance(formatter, MarkdownFormatter)

    def test_get_formatter_by_alias(self):
        """Test getting formatter by alias."""
        # 'md' should map to markdown
        formatter = get_formatter("md")
        assert isinstance(formatter, MarkdownFormatter)

    def test_invalid_formatter(self):
        """Test getting invalid formatter."""
        formatter = get_formatter("invalid_format")
        assert formatter is None
