import logging
from ocs_ci.framework import config
from ocs_ci.ocs.constants import OPENSHIFT_DEDICATED_PLATFORM

log = logging.getLogger(__name__)


def pytest_collection_modifyitems(items):
    """
    A pytest hook to filter out mcg tests
    when running on openshift dedicated platform
    Args:
        items: list of collected tests
    """
    if (
        config.ENV_DATA["platform"].lower() == OPENSHIFT_DEDICATED_PLATFORM
        and float(config.ENV_DATA["ocs_version"]) < 4.8
    ):
        for item in items.copy():
            if "manage/mcg" in str(item.fspath):
                log.info(
                    f"Test {item} is removed from the collected items"
                    f" mcg is not supported on {config.ENV_DATA['platform'].lower()}"
                    f" for OCS version ({config.ENV_DATA['ocs_version']}) being lower than 4.8"
                )
                items.remove(item)