from helpers.dependency_install import BASE_PACKAGES


def test_system_dependencies_include_xdpyinfo_provider():
    assert "x11-utils" in BASE_PACKAGES
