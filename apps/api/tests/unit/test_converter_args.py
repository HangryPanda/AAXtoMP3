"""Unit tests for ConverterEngine argument generation."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from services.converter_engine import ConverterEngine

class TestConverterArguments:
    """Tests for verifying command line arguments passed to AAXtoMP3."""

    @pytest.fixture
    def engine(self):
        with patch("services.converter_engine.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                aaxtomp3_path=Path("/scripts/AAXtoMP3"),
            )
            return ConverterEngine()

    def test_output_dir_flag(self, engine, tmp_path):
        """
        Verify that the output directory is passed with --target_dir
        and NOT -d (which enables debug mode in AAXtoMP3).
        """
        input_file = tmp_path / "book.aaxc"
        output_dir = tmp_path / "output"
        
        cmd = engine.build_command(
            input_file=input_file,
            output_dir=output_dir,
        )
        
        # Check for correct flag
        assert "--target_dir" in cmd, "Command should use --target_dir for output directory"
        
        # Verify the path follows the flag
        idx = cmd.index("--target_dir")
        assert cmd[idx + 1] == str(output_dir), "Output directory path should follow --target_dir flag"
        
        # Check that -d is NOT present (unless specifically intended for debug, which isn't standard here)
        assert "-d" not in cmd, "Command should not use -d flag (debug mode) for output directory"

    def test_use_audible_cli_data_flag(self, engine, tmp_path):
        """Verify that --use-audible-cli-data is used when a voucher is present."""
        input_file = tmp_path / "book.aaxc"
        voucher_file = tmp_path / "book.voucher"
        voucher_file.touch()
        
        cmd = engine.build_command(
            input_file=input_file,
            output_dir=tmp_path,
            voucher_file=voucher_file
        )
        
        assert "--use-audible-cli-data" in cmd, "Should include --use-audible-cli-data when voucher is present"
        assert "-A" not in cmd, "Should not include -A (authcode) when using voucher"

    def test_authcode_flag(self, engine, tmp_path):
        """Verify that -A is used when authcode is provided without voucher."""
        input_file = tmp_path / "book.aax"
        
        cmd = engine.build_command(
            input_file=input_file,
            output_dir=tmp_path,
            authcode="cafebabe"
        )
        
        assert "-A" in cmd, "Should include -A flag for authcode"
        idx = cmd.index("-A")
        assert cmd[idx + 1] == "cafebabe", "Authcode value should follow -A flag"

    def test_naming_scheme_flags(self, engine, tmp_path):
        """Verify naming scheme flags."""
        input_file = tmp_path / "book.aax"
        
        cmd = engine.build_command(
            input_file=input_file,
            output_dir=tmp_path,
            dir_naming_scheme="scheme1",
            file_naming_scheme="scheme2"
        )
        
        assert "--dir-naming-scheme" in cmd
        assert cmd[cmd.index("--dir-naming-scheme") + 1] == "scheme1"
        
        assert "--file-naming-scheme" in cmd
        assert cmd[cmd.index("--file-naming-scheme") + 1] == "scheme2"

    def test_input_file_is_last(self, engine, tmp_path):
        """Verify input file is always the last argument."""
        input_file = tmp_path / "book.aax"
        
        cmd = engine.build_command(
            input_file=input_file,
            output_dir=tmp_path,
        )
        
        assert cmd[-1] == str(input_file), "Input file must be the last argument"
