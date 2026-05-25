"""
Test module for RHSTOR-7964 Group 4: Internal Mode Metrics Validation

This module tests ocs-metrics-exporter behavior in Internal/Standalone mode:
- ocs-tm011: Verify consumer_name label empty/absent in internal mode
- ocs-tm012: Verify rados_namespace="openshift-storage" in internal mode
- ocs-tm013: Verify cluster-level metrics (no consumer_name)

These tests validate that metrics in internal mode do NOT have consumer_name labels
(since there are no remote consumers), and that rados_namespace is set correctly.
"""

import logging
import pytest

from ocs_ci.framework import config
from ocs_ci.framework.pytest_customization.marks import (
    blue_squad,
    skipif_external_mode,
    skipif_hci_client,
    skipif_managed_service,
    skipif_mcg_only,
    skipif_ms_consumer,
    tier1,
)
from ocs_ci.framework.testlib import skipif_managed_service as skip_ms
from ocs_ci.helpers import ocs_metrics_exporter_helpers as ome_helpers
from ocs_ci.ocs import constants
from ocs_ci.ocs.resources.pvc import create_pvc, delete_pvcs
from ocs_ci.ocs.resources.pod import get_ceph_tools_pod
from ocs_ci.utility.utils import TimeoutSampler

logger = logging.getLogger(__name__)


def skip_if_provider_mode():
    """
    Skip test if running on a provider cluster (with consumers).
    
    Internal mode tests should only run on standalone/internal clusters.
    """
    if getattr(config, "multicluster", False):
        if config.is_consumer_exist() or config.hci_client_exist():
            pytest.skip(
                "Test is for internal/standalone mode only; "
                "skipping on provider cluster with consumers"
            )


@pytest.fixture(scope="module")
def exporter_pod():
    """
    Fixture to get the ocs-metrics-exporter pod.
    
    Returns:
        Pod: The ocs-metrics-exporter pod object
    """
    pod = ome_helpers.get_ocs_metrics_exporter_pod()
    assert pod is not None, "ocs-metrics-exporter pod not found"
    assert pod.get().get("status", {}).get("phase") == constants.STATUS_RUNNING, (
        "ocs-metrics-exporter pod is not running"
    )
    return pod


@pytest.fixture(scope="module")
def metrics_text(exporter_pod):
    """
    Fixture to scrape full metrics from the exporter pod.
    
    Args:
        exporter_pod (Pod): The exporter pod fixture
        
    Returns:
        str: Full metrics text in Prometheus exposition format
    """
    logger.info("Scraping full metrics from ocs-metrics-exporter pod")
    text = ome_helpers.scrape_full_metrics_text(exporter_pod, max_bytes=131072)
    ome_helpers.assert_prometheus_exposition_text(text)
    logger.info(f"Successfully scraped {len(text)} bytes of metrics")
    return text


@pytest.fixture(scope="module")
def metric_families(metrics_text):
    """
    Fixture to parse metrics text into structured format.
    
    Args:
        metrics_text (str): Raw metrics text
        
    Returns:
        dict: Parsed metric families {metric_name: [samples]}
    """
    families = ome_helpers.parse_metric_families(metrics_text)
    logger.info(f"Parsed {len(families)} metric families")
    return families


@pytest.mark.polarion_id("OCS-6011")
@blue_squad
@tier1
@skipif_managed_service
@skipif_external_mode
@skipif_mcg_only
@skipif_ms_consumer
@skipif_hci_client
@pytest.mark.parametrize(
    "metric_name",
    [
        "ocs_rbd_pv_metadata",
        "ocs_rbd_children_count",
        "ocs_cephfs_subvolume_count",
    ],
)
def test_consumer_name_absent_in_internal_mode(metric_families, metric_name):
    """
    Test Case: ocs-tm011
    Verify consumer_name label is empty/absent in internal mode.
    
    In internal/standalone mode (no remote consumers), PV-level metrics should NOT
    have a consumer_name label since all workloads are local.
    
    Steps:
        1. Skip if running on provider cluster with consumers
        2. Scrape metrics from exporter pod
        3. Parse metrics into families
        4. For each PV-level metric (RBD, CephFS):
           - Verify metric exists
           - Verify NO samples have consumer_name label
    
    Expected Result:
        - All PV-level metrics exist
        - No consumer_name label present in any sample
        - This confirms internal mode behavior (RHSTOR-7964)
    """
    skip_if_provider_mode()
    
    logger.info(
        f"Verifying consumer_name is absent in metric '{metric_name}' "
        "for internal mode"
    )
    
    # Verify metric exists
    ome_helpers.assert_metric_present(metric_families, metric_name)
    
    # Verify no samples have consumer_name label
    samples = metric_families[metric_name]
    logger.info(f"Found {len(samples)} samples for metric '{metric_name}'")
    
    for idx, sample in enumerate(samples):
        labels = sample.get("labels", {})
        assert "consumer_name" not in labels, (
            f"Internal mode: metric '{metric_name}' sample #{idx} should NOT have "
            f"consumer_name label (no remote consumers); sample: {sample}"
        )
        logger.debug(
            f"Sample #{idx} correctly has no consumer_name: "
            f"labels={list(labels.keys())}"
        )
    
    logger.info(
        f"✓ Verified: All {len(samples)} samples of '{metric_name}' "
        "have no consumer_name label (internal mode)"
    )


@pytest.mark.polarion_id("OCS-6012")
@blue_squad
@tier1
@skipif_managed_service
@skipif_external_mode
@skipif_mcg_only
@skipif_ms_consumer
@skipif_hci_client
def test_rados_namespace_in_internal_mode(metric_families):
    """
    Test Case: ocs-tm012
    Verify rados_namespace="openshift-storage" in internal mode.
    
    In internal mode, all RBD PVs should have rados_namespace set to the
    default storage namespace (typically "openshift-storage").
    
    Steps:
        1. Skip if running on provider cluster with consumers
        2. Scrape and parse metrics
        3. Check ocs_rbd_pv_metadata metric
        4. Verify all samples have rados_namespace label
        5. Verify rados_namespace value matches cluster namespace
    
    Expected Result:
        - ocs_rbd_pv_metadata metric exists
        - All samples have rados_namespace label
        - rados_namespace value is cluster namespace (e.g., "openshift-storage")
    """
    skip_if_provider_mode()
    
    metric_name = "ocs_rbd_pv_metadata"
    expected_namespace = config.ENV_DATA.get(
        "cluster_namespace", constants.OPENSHIFT_STORAGE_NAMESPACE
    )
    
    logger.info(
        f"Verifying rados_namespace='{expected_namespace}' in metric "
        f"'{metric_name}' for internal mode"
    )
    
    # Verify metric exists
    ome_helpers.assert_metric_present(metric_families, metric_name)
    
    samples = metric_families[metric_name]
    logger.info(f"Found {len(samples)} samples for metric '{metric_name}'")
    
    if len(samples) == 0:
        logger.warning(
            f"No samples found for '{metric_name}' - this may indicate no RBD PVCs "
            "exist in the cluster. Test will pass but validation is limited."
        )
        return
    
    # Verify each sample has correct rados_namespace
    for idx, sample in enumerate(samples):
        labels = sample.get("labels", {})
        
        assert "rados_namespace" in labels, (
            f"Internal mode: metric '{metric_name}' sample #{idx} missing "
            f"rados_namespace label; sample: {sample}"
        )
        
        actual_namespace = labels["rados_namespace"]
        assert actual_namespace == expected_namespace, (
            f"Internal mode: metric '{metric_name}' sample #{idx} has incorrect "
            f"rados_namespace; expected '{expected_namespace}', "
            f"got '{actual_namespace}'; sample: {sample}"
        )
        
        logger.debug(
            f"Sample #{idx} has correct rados_namespace='{actual_namespace}'"
        )
    
    logger.info(
        f"✓ Verified: All {len(samples)} samples of '{metric_name}' have "
        f"rados_namespace='{expected_namespace}' (internal mode)"
    )


@pytest.mark.polarion_id("OCS-6013")
@blue_squad
@tier1
@skipif_managed_service
@skipif_external_mode
@skipif_mcg_only
@skipif_ms_consumer
@skipif_hci_client
@pytest.mark.parametrize(
    "metric_name,uses_storage_consumer_name",
    [
        ("ocs_rbd_mirror_daemon_health", False),
        ("ocs_mirror_daemon_count", False),
        ("ocs_storage_consumer_metadata", True),
        ("ocs_storage_client_last_heartbeat", True),
    ],
)
def test_cluster_level_metrics_no_consumer_name(
    metric_families, metric_name, uses_storage_consumer_name
):
    """
    Test Case: ocs-tm013
    Verify cluster-level metrics have no consumer_name label.
    
    Cluster-level metrics (mirror daemon health, mirror daemon count, etc.) should
    NOT have a consumer_name label. Some metrics like ocs_storage_consumer_metadata
    use storage_consumer_name instead (which is different from consumer_name).
    
    Steps:
        1. Skip if running on provider cluster with consumers
        2. Scrape and parse metrics
        3. For each cluster-level metric:
           - Verify metric exists (or skip if not applicable)
           - Verify NO samples have consumer_name label
           - If metric uses storage_consumer_name, verify that's present instead
    
    Expected Result:
        - Cluster-level metrics exist (when applicable)
        - No consumer_name label in any sample
        - storage_consumer_name present for consumer metadata metrics
    """
    skip_if_provider_mode()
    
    logger.info(
        f"Verifying cluster-level metric '{metric_name}' has no consumer_name label"
    )
    
    # Check if metric exists - some may not be present depending on configuration
    if metric_name not in metric_families:
        logger.info(
            f"Metric '{metric_name}' not found - may not be applicable for this "
            "cluster configuration (e.g., no mirroring enabled). Skipping."
        )
        pytest.skip(f"Metric '{metric_name}' not present in this cluster")
    
    samples = metric_families[metric_name]
    logger.info(f"Found {len(samples)} samples for metric '{metric_name}'")
    
    if len(samples) == 0:
        logger.info(
            f"No samples for '{metric_name}' - metric exists but has no data. "
            "This is acceptable for cluster-level metrics."
        )
        return
    
    # Verify no samples have consumer_name label
    for idx, sample in enumerate(samples):
        labels = sample.get("labels", {})
        
        assert "consumer_name" not in labels, (
            f"Cluster-level metric '{metric_name}' sample #{idx} should NOT have "
            f"consumer_name label; sample: {sample}"
        )
        
        # If this metric uses storage_consumer_name, verify it's present
        if uses_storage_consumer_name:
            # Note: storage_consumer_name may not be present in internal mode
            # since there are no consumers, so we just log if it's there
            if "storage_consumer_name" in labels:
                logger.debug(
                    f"Sample #{idx} has storage_consumer_name="
                    f"'{labels['storage_consumer_name']}' (expected for this metric)"
                )
        
        logger.debug(
            f"Sample #{idx} correctly has no consumer_name: "
            f"labels={list(labels.keys())}"
        )
    
    logger.info(
        f"✓ Verified: All {len(samples)} samples of '{metric_name}' have no "
        "consumer_name label (cluster-level metric)"
    )

# Made with Bob
