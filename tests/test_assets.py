import pytest

from skillgen.assets import find_data_folder
from skillgen.errors import WorkspaceError


def test_find_data_folder_finds_shipped_data():
    assert (find_data_folder("hintpacks") / "README.md").is_file()
    assert (find_data_folder("claude") / "commands" / "command.md").is_file()


def test_find_data_folder_reports_missing():
    with pytest.raises(WorkspaceError, match="reinstall"):
        find_data_folder("nothing-here")
