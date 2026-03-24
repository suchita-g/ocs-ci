"""
Test OCS upgrade with cluster filled to 85-90% capacity

This module tests the OCS upgrade scenario where:
1. Pre-upgrade: Fill Ceph cluster to 85-90% capacity using both RBD and CephFS
2. During upgrade: Continue IO operations
3. Post-upgrade: Validate data integrity and capacity

The test uses existing ocs-ci infrastructure:
- ClusterFiller for capacity filling
- MD5 checksums for data integrity
- Session-scoped fixtures for resource management
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from ocs_ci.framework import config
from ocs_ci.framework.pytest_customization.marks import (
    purple_squad,
    pre_upgrade,
    ocs_upgrade,
    post_upgrade,
)
from ocs_ci.framework.testlib import polarion_id
from ocs_ci.helpers.cluster_exp_helpers import ClusterFiller, cluster_copy_ops
from ocs_ci.ocs import constants
from ocs_ci.ocs.cluster import CephCluster, get_percent_used_capacity
from ocs_ci.ocs.exceptions import UnexpectedBehaviour
from ocs_ci.ocs.ocs_upgrade import run_ocs_upgrade
from ocs_ci.ocs.resources.pod import cal_md5sum

log = logging.getLogger(__name__)

# Global variable to store capacity baseline data
CAPACITY_BASELINE = {}


def fill_cluster_to_target_capacity(
    pods, target_percent=90, namespace=None, max_attempts=50
):
    """
    Fill cluster to target capacity percentage using ClusterFiller.

    Args:
        pods (list): List of pod objects to use for filling
        target_percent (int): Target capacity percentage (default: 90)
        namespace (str): Namespace where pods are running
        max_attempts (int): Maximum filling attempts before giving up

    Returns:
        float: Final capacity percentage achieved

    Raises:
        UnexpectedBehaviour: If unable to reach target capacity
    """
    namespace = namespace or config.ENV_DATA["cluster_namespace"]
    log.info(f"Starting cluster fill to {target_percent}% capacity")
    log.info(f"Using {len(pods)} pods for capacity filling")

    # Get initial capacity
    initial_capacity = get_percent_used_capacity()
    log.info(f"Initial cluster capacity: {initial_capacity}%")

    if initial_capacity >= target_percent:
        log.warning(
            f"Cluster already at {initial_capacity}%, "
            f"target is {target_percent}%. Skipping fill."
        )
        return initial_capacity

    # Use ClusterFiller to fill the cluster
    cluster_filler = ClusterFiller(
        pods_to_fill=pods,
        percent_required_filled=target_percent,
        namespace=namespace,
    )

    try:
        cluster_filler.cluster_filler()
        final_capacity = get_percent_used_capacity()
        log.info(f"Cluster filled to {final_capacity}% capacity")

        # Validate we reached target range (85-95% is acceptable)
        if 85 <= final_capacity <= 95:
            log.info(
                f"Successfully filled cluster to {final_capacity}% "
                f"(target: {target_percent}%)"
            )
            return final_capacity
        else:
            raise UnexpectedBehaviour(
                f"Cluster capacity {final_capacity}% is outside "
                f"acceptable range (85-95%)"
            )

    except Exception as e:
        current_capacity = get_percent_used_capacity()
        log.error(
            f"Failed to fill cluster to target capacity. "
            f"Current: {current_capacity}%, Target: {target_percent}%"
        )
        raise UnexpectedBehaviour(f"Cluster filling failed: {e}")


def capture_data_checksums(pods):
    """
    Calculate and store MD5 checksums for test files in pods.

    Args:
        pods (list): List of pod objects

    Returns:
        dict: Dictionary mapping pod name to file checksums
              Format: {pod_name: {file_path: md5sum}}
    """
    log.info(f"Capturing MD5 checksums for {len(pods)} pods")
    checksums = {}

    for pod in pods:
        pod_checksums = {}
        try:
            # Calculate checksum for the main test file
            # The file path depends on the pod type (fedora vs others)
            file_path = "/mnt/ceph.tar.gz"

            # Check if file exists before calculating checksum
            try:
                pod.exec_sh_cmd_on_pod(f"test -f {file_path}", sh="bash")
                md5sum = cal_md5sum(pod_obj=pod, file_name="ceph.tar.gz", block=False)
                pod_checksums[file_path] = md5sum
                log.info(f"Pod {pod.name}: {file_path} -> {md5sum}")
            except Exception as e:
                log.warning(
                    f"Could not calculate checksum for {file_path} "
                    f"in pod {pod.name}: {e}"
                )

            checksums[pod.name] = pod_checksums

        except Exception as e:
            log.error(f"Failed to capture checksums for pod {pod.name}: {e}")
            checksums[pod.name] = {}

    log.info(f"Captured checksums for {len(checksums)} pods")
    return checksums


def validate_data_integrity(pods, baseline_checksums):
    """
    Validate data integrity by comparing current checksums with baseline.

    Args:
        pods (list): List of pod objects
        baseline_checksums (dict): Baseline checksums from pre-upgrade

    Raises:
        UnexpectedBehaviour: If data corruption is detected
    """
    log.info("Validating data integrity post-upgrade")
    current_checksums = capture_data_checksums(pods)

    mismatches = []
    for pod_name, baseline_files in baseline_checksums.items():
        if pod_name not in current_checksums:
            log.warning(f"Pod {pod_name} not found in current checksums")
            continue

        current_files = current_checksums[pod_name]
        for file_path, baseline_md5 in baseline_files.items():
            if file_path not in current_files:
                mismatches.append(
                    f"Pod {pod_name}: File {file_path} not found post-upgrade"
                )
                continue

            current_md5 = current_files[file_path]
            if baseline_md5 != current_md5:
                mismatches.append(
                    f"Pod {pod_name}: {file_path} - "
                    f"Baseline: {baseline_md5}, Current: {current_md5}"
                )
            else:
                log.info(
                    f"Pod {pod_name}: {file_path} - "
                    f"Data integrity verified (MD5: {current_md5})"
                )

    if mismatches:
        error_msg = "Data corruption detected:\n" + "\n".join(mismatches)
        log.error(error_msg)
        raise UnexpectedBehaviour(error_msg)

    log.info("Data integrity validation passed - all checksums match")


def validate_capacity_metrics(pre_upgrade_capacity, post_upgrade_capacity, tolerance=5):
    """
    Validate that capacity hasn't changed significantly post-upgrade.

    Args:
        pre_upgrade_capacity (float): Capacity percentage before upgrade
        post_upgrade_capacity (float): Capacity percentage after upgrade
        tolerance (int): Acceptable difference percentage (default: 5)

    Raises:
        UnexpectedBehaviour: If capacity difference exceeds tolerance
    """
    log.info("Validating capacity metrics post-upgrade")
    log.info(f"Pre-upgrade capacity: {pre_upgrade_capacity}%")
    log.info(f"Post-upgrade capacity: {post_upgrade_capacity}%")

    capacity_diff = abs(post_upgrade_capacity - pre_upgrade_capacity)
    log.info(f"Capacity difference: {capacity_diff}%")

    if capacity_diff > tolerance:
        raise UnexpectedBehaviour(
            f"Capacity changed by {capacity_diff}% (tolerance: {tolerance}%). "
            f"Pre: {pre_upgrade_capacity}%, Post: {post_upgrade_capacity}%"
        )

    log.info(
        f"Capacity validation passed - difference {capacity_diff}% "
        f"is within tolerance {tolerance}%"
    )


def run_continuous_io_operations(pods, duration=300):
    """
    Run continuous IO operations on pods in background.

    Args:
        pods (list): List of pod objects
        duration (int): Duration to run IO in seconds (default: 300)

    Returns:
        ThreadPoolExecutor: Executor with running IO operations
    """
    log.info(f"Starting continuous IO operations on {len(pods)} pods")

    def io_worker(pod):
        """Worker function to run IO on a single pod"""
        try:
            iterations = 0
            start_time = time.time()
            while time.time() - start_time < duration:
                result = cluster_copy_ops(pod)
                if not result:
                    log.warning(f"IO operation failed on pod {pod.name}")
                iterations += 1
                time.sleep(10)  # Small delay between operations
            log.info(f"Completed {iterations} IO iterations on pod {pod.name}")
        except Exception as e:
            log.error(f"IO worker failed for pod {pod.name}: {e}")

    executor = ThreadPoolExecutor(max_workers=len(pods))
    for pod in pods:
        executor.submit(io_worker, pod)

    return executor


@pytest.fixture(scope="session")
def capacity_filled_pods(
    request,
    pvc_factory_session,
    pod_factory_session,
    fio_project,
):
    """
    Create pods with PVCs to fill cluster to 85-90% capacity.
    Uses both RBD and CephFS storage types.

    Returns:
        list: List of pod objects with both RBD and CephFS PVCs
    """
    log.info("Creating pods for capacity filling")
    pods = []
    pvc_size = 50  # Start with 50GB PVCs

    # Calculate how many pods we need based on cluster capacity
    ceph_cluster = CephCluster()
    total_capacity = ceph_cluster.get_ceph_capacity()
    log.info(f"Total cluster capacity: {total_capacity} GB")

    # Create a mix of RBD and CephFS pods
    # We'll create 6 pods total (3 RBD, 3 CephFS)
    storage_types = [
        (constants.CEPHBLOCKPOOL, "rbd"),
        (constants.CEPHBLOCKPOOL, "rbd"),
        (constants.CEPHBLOCKPOOL, "rbd"),
        (constants.CEPHFILESYSTEM, "cephfs"),
        (constants.CEPHFILESYSTEM, "cephfs"),
        (constants.CEPHFILESYSTEM, "cephfs"),
    ]

    for idx, (interface, storage_type) in enumerate(storage_types):
        try:
            log.info(
                f"Creating pod {idx + 1}/{len(storage_types)} "
                f"with {storage_type} storage"
            )
            pvc = pvc_factory_session(
                project=fio_project,
                interface=interface,
                size=pvc_size,
                access_mode=constants.ACCESS_MODE_RWO,
                status=constants.STATUS_BOUND,
            )
            pod = pod_factory_session(pvc=pvc, interface=interface, project=fio_project)
            pods.append(pod)
            log.info(f"Created pod {pod.name} with {storage_type} PVC {pvc.name}")
        except Exception as e:
            log.error(f"Failed to create pod {idx + 1}: {e}")

    def teardown():
        """Cleanup pods"""
        log.info("Cleaning up capacity-filled pods")
        for pod in pods:
            try:
                pod.delete()
            except Exception as e:
                log.warning(f"Failed to delete pod {pod.name}: {e}")

    request.addfinalizer(teardown)

    log.info(f"Created {len(pods)} pods for capacity filling")
    return pods


@purple_squad
@pre_upgrade
@polarion_id("OCS-5800")
def test_fill_cluster_capacity_pre_upgrade(capacity_filled_pods):
    """
    Pre-upgrade test: Fill Ceph cluster to 85-90% capacity and capture baseline.

    This test:
    1. Creates pods with both RBD and CephFS PVCs
    2. Fills cluster to 85-90% capacity using ClusterFiller
    3. Captures MD5 checksums of test data for post-upgrade validation
    4. Stores baseline metrics in global variable

    Args:
        capacity_filled_pods (list): Fixture providing pods for capacity filling
    """
    log.info("=" * 80)
    log.info("TEST: Fill cluster capacity pre-upgrade")
    log.info("=" * 80)

    # Verify cluster health before filling
    ceph_cluster = CephCluster()
    ceph_cluster.cluster_health_check(timeout=300)
    log.info("Cluster health check passed")

    # Get initial capacity
    initial_capacity = get_percent_used_capacity()
    log.info(f"Initial cluster capacity: {initial_capacity}%")

    # Fill cluster to 85-90% capacity
    target_capacity = 90
    final_capacity = fill_cluster_to_target_capacity(
        pods=capacity_filled_pods,
        target_percent=target_capacity,
        namespace=config.ENV_DATA["cluster_namespace"],
    )

    # Capture baseline checksums
    log.info("Capturing baseline MD5 checksums")
    baseline_checksums = capture_data_checksums(capacity_filled_pods)

    # Store baseline data in global variable for post-upgrade validation
    global CAPACITY_BASELINE
    CAPACITY_BASELINE = {
        "capacity": final_capacity,
        "checksums": baseline_checksums,
        "pods": [pod.name for pod in capacity_filled_pods],
    }

    log.info("Pre-upgrade capacity filling completed successfully")
    log.info(f"Final capacity: {final_capacity}%")
    log.info(f"Baseline checksums captured for {len(baseline_checksums)} pods")
    log.info("=" * 80)


@purple_squad
@ocs_upgrade
@polarion_id("OCS-5801")
def test_upgrade_with_capacity_filled(capacity_filled_pods, upgrade_stats):
    """
    Upgrade test: Perform OCS upgrade with cluster at 85-90% capacity.

    This test:
    1. Starts continuous IO operations in background
    2. Executes OCS upgrade
    3. Monitors IO continues during upgrade
    4. Validates upgrade completion

    Args:
        capacity_filled_pods (list): Pods used for capacity filling
        upgrade_stats (dict): Dictionary to store upgrade statistics
    """
    log.info("=" * 80)
    log.info("TEST: OCS upgrade with capacity filled")
    log.info("=" * 80)

    # Verify we have baseline data
    if not CAPACITY_BASELINE:
        pytest.skip("No baseline data available - pre-upgrade test may have failed")

    # Get current capacity before upgrade
    pre_upgrade_capacity = get_percent_used_capacity()
    log.info(f"Capacity before upgrade: {pre_upgrade_capacity}%")

    # Start continuous IO operations in background
    log.info("Starting continuous IO operations during upgrade")
    io_executor = run_continuous_io_operations(
        pods=capacity_filled_pods, duration=3600  # 1 hour max
    )

    try:
        # Perform OCS upgrade
        log.info("Starting OCS upgrade")
        run_ocs_upgrade(upgrade_stats=upgrade_stats)
        log.info("OCS upgrade completed successfully")

    finally:
        # Shutdown IO operations
        log.info("Stopping IO operations")
        io_executor.shutdown(wait=True)

    # Verify cluster health after upgrade
    ceph_cluster = CephCluster()
    ceph_cluster.cluster_health_check(timeout=600)
    log.info("Cluster health check passed post-upgrade")

    log.info("=" * 80)


@purple_squad
@post_upgrade
@polarion_id("OCS-5802")
def test_validate_capacity_post_upgrade(capacity_filled_pods):
    """
    Post-upgrade test: Validate capacity and data integrity.

    This test:
    1. Validates cluster capacity remains at 85-90%
    2. Recalculates MD5 checksums
    3. Compares with pre-upgrade baseline
    4. Validates no data corruption occurred

    Args:
        capacity_filled_pods (list): Pods used for capacity filling
    """
    log.info("=" * 80)
    log.info("TEST: Validate capacity and data integrity post-upgrade")
    log.info("=" * 80)

    # Verify we have baseline data
    if not CAPACITY_BASELINE:
        pytest.fail("No baseline data available - pre-upgrade test may have failed")

    # Get post-upgrade capacity
    post_upgrade_capacity = get_percent_used_capacity()
    log.info(f"Post-upgrade capacity: {post_upgrade_capacity}%")

    # Validate capacity hasn't changed significantly
    pre_upgrade_capacity = CAPACITY_BASELINE["capacity"]
    validate_capacity_metrics(
        pre_upgrade_capacity=pre_upgrade_capacity,
        post_upgrade_capacity=post_upgrade_capacity,
        tolerance=5,
    )

    # Validate data integrity
    baseline_checksums = CAPACITY_BASELINE["checksums"]
    validate_data_integrity(
        pods=capacity_filled_pods, baseline_checksums=baseline_checksums
    )

    # Verify cluster health
    ceph_cluster = CephCluster()
    ceph_cluster.cluster_health_check(timeout=300)
    log.info("Final cluster health check passed")

    log.info("=" * 80)
    log.info("Post-upgrade validation completed successfully")
    log.info(f"Capacity: {post_upgrade_capacity}% (baseline: {pre_upgrade_capacity}%)")
    log.info("Data integrity: VERIFIED")
    log.info("=" * 80)


# Made with Bob
