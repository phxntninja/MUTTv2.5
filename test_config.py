import unittest
from unittest.mock import patch, mock_open
import yaml
from mutt.config import load_config

class TestConfig(unittest.TestCase):
    @patch("builtins.open", new_callable=mock_open, read_data="network:\n  port: 514")
    @patch("yaml.safe_load")
    def test_load_config_success(self, mock_yaml_load, mock_file):
        mock_yaml_load.return_value = {"network": {"port": 514}}
        config = load_config("dummy.yaml")
        self.assertEqual(config["network"]["port"], 514)
        mock_file.assert_called_with("dummy.yaml", "r", encoding="utf-8")

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_load_config_not_found(self, mock_file):
        with self.assertRaises(FileNotFoundError):
            load_config("missing.yaml")

    @patch("builtins.open", new_callable=mock_open, read_data="invalid: yaml:")
    @patch("yaml.safe_load", side_effect=yaml.YAMLError("error"))
    def test_load_config_yaml_error(self, mock_yaml_load, mock_file):
        with self.assertRaises(yaml.YAMLError):
            load_config("invalid.yaml")

if __name__ == "__main__":
    unittest.main()
