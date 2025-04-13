"""Pytest adoption of command line configuration."""


def pytest_addoption(parser):
    parser.addoption(
        "--source-root",
        action="store",
        default="./tests/data",
        help="The base directory for test input files (default: ./tests/data)"
    )
    parser.addoption(
        "--storage-root",
        action="store",
        default="./tests/data",
        help="The storage directory for test state files (default: tmp_path)"
    )
