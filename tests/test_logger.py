import io
import logging
import os
import sys
import unittest

from app.utils.logger import LOGGER_NAME, configure_logger, get_logger


class LoggerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = logging.getLogger(LOGGER_NAME)
        self.original_handlers = list(self.logger.handlers)
        self.original_level = self.logger.level
        self.original_propagate = self.logger.propagate
        self.original_log_level = os.environ.get("LOG_LEVEL")
        self.logger.handlers = []
        os.environ.pop("LOG_LEVEL", None)

    def tearDown(self) -> None:
        self.logger.handlers = self.original_handlers
        self.logger.setLevel(self.original_level)
        self.logger.propagate = self.original_propagate
        if self.original_log_level is None:
            os.environ.pop("LOG_LEVEL", None)
        else:
            os.environ["LOG_LEVEL"] = self.original_log_level
        configure_logger(stream=sys.stdout)

    def test_configure_logger_is_idempotent(self) -> None:
        stream = io.StringIO()

        logger = configure_logger(level_name="DEBUG", stream=stream)
        configure_logger(level_name="DEBUG", stream=stream)
        logger.debug("single debug line")

        self.assertEqual(len(logger.handlers), 1)
        self.assertEqual(stream.getvalue().count("single debug line"), 1)

    def test_log_level_env_configures_output(self) -> None:
        stream = io.StringIO()
        os.environ["LOG_LEVEL"] = "INFO"

        logger = configure_logger(stream=stream)
        logger.debug("hidden debug line")
        logger.info("visible info line")

        output = stream.getvalue()
        self.assertNotIn("hidden debug line", output)
        self.assertIn("visible info line", output)

    def test_get_logger_supports_debug_output_by_default(self) -> None:
        stream = io.StringIO()
        configure_logger(stream=stream)

        logger = get_logger("tests")
        logger.debug("default debug line")

        self.assertIn("default debug line", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
