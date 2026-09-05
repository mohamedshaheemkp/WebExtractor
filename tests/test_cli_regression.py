import unittest
import importlib

from webextractor.generator.project import ReactProjectGenerator


class TestCLIRegression(unittest.TestCase):
    """
    Regression test verifying CLI rip command imports and resolves ReactProjectGenerator.
    """

    def test_cli_rip_imports_react_project_generator(self):
        # Import rip command module dynamically to ensure clean import resolution
        rip_module = importlib.import_module("webextractor.cli.commands.rip")

        self.assertTrue(hasattr(rip_module, "ReactProjectGenerator"))
        self.assertIs(rip_module.ReactProjectGenerator, ReactProjectGenerator)

    def test_cli_rip_uses_site_analyzer_and_site_ir(self):
        rip_module = importlib.import_module("webextractor.cli.commands.rip")
        self.assertTrue(hasattr(rip_module, "SiteAnalyzer"))
        self.assertTrue(hasattr(rip_module, "SiteIR"))

    def test_cli_main_help_parser(self):
        cli_module = importlib.import_module("webextractor.cli")
        parser = cli_module.build_parser()

        subparsers_actions = [
            action for action in parser._actions
            if action.__class__.__name__ == "_SubParsersAction"
        ]
        self.assertTrue(len(subparsers_actions) > 0)
        choices = subparsers_actions[0].choices
        self.assertIn("rip", choices)
        rip_parser = choices["rip"]
        self.assertIsNotNone(rip_parser)


if __name__ == "__main__":
    unittest.main()
