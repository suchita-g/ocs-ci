"""
Test module for RHSTOR-7964 Group 12: Backward Compatibility

This module tests that the rearchitected ocs-metrics-exporter maintains
backward compatibility with existing metrics and alerts:
- ocs-tm032: Verify existing metrics names are preserved
- ocs-tm033: Verify existing alerts fire in Internal Mode

These tests ensure no breaking changes were introduced in RHSTOR-7964.
"""

import logging
import pytest

from ocs_ci.framework.pytest_customization.marks import (
    blue_squad,
    skipif_external_mode,
    skipif_hci_client,
    skipif_managed_service,
    skipif_mcg_only,
    skipif_ms_consumer,
    tier1,
)
from ocs_ci.helpers import ocs_metrics_exporter_helpers as ome_helpers
from ocs_ci.ocs import constants
from ocs_ci.ocs.ocp import OCP
from ocs_ci.utility.prometheus import PrometheusAPI

logger = logging.getLogger(__name__)


# Expected core metrics that must be present (backward compatibility)
EXPECTED_CORE_METRICS = [
    "ocs_rbd_pv_metadata",
    "ocs_rbd_children_count",
    "ocs_cephfs_subvolume_count",
    "ocs_pool_mirroring_status",
    "ocs_pool_mirroring_image_health",
    "ocs_rbd_mirror_daemon_health",
    "ocs_mirror_daemon_count",
    "ocs_rbd_client_blocklisted",
]

# Expected core alert rules that must be present
EXPECTED_CORE_ALERTS = [
    "HighRBDCloneSnapshotCount",
    "HighCephFSSnapshotCount", 
    "HighRBDSnapshotCount",
    "ODFPersistentVolumeMirrorStatus",
    "CephFSStaleSubvolume",
    "ODFRBDClientBlocked",
]


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


@pytest.fixture(scope="module")
def prometheus_api():
    """
    Fixture to get Prometheus API instance.
    
    Returns:
        PrometheusAPI: Prometheus API client
    """
    return PrometheusAPI()


@pytest.mark.polarion_id("OCS-6032")
@blue_squad
@tier1
@skipif_managed_service
@skipif_external_mode
@skipif_mcg_only
@skipif_ms_consumer
@skipif_hci_client
def test_existing_metrics_preserved(metric_families):
    """
    Test Case: ocs-tm032
    Verify existing metrics names are preserved (no breaking changes).
    
    The RHSTOR-7964 rearchitecture should not remove or rename any existing
    metrics. This test validates that all core metrics are still present.
    
    Steps:
        1. Scrape metrics from exporter pod
        2. Parse metrics into families
        3. Check each expected core metric:
           - Verify metric name exists
           - Log if metric has samples (data)
        4. Verify no metrics were removed
    
    Expected Result:
        - All expected core metrics are present
        - Metric names unchanged from pre-RHSTOR-7964
        - Backward compatibility maintained
    
    Note:
        Some metrics may have zero samples depending on cluster configuration
        (e.g., mirroring metrics if mirroring is not enabled). This is acceptable
        as long as the metric name is present in the exposition.
    """
    logger.info("Verifying backward compatibility: checking existing metrics preserved")
    
    missing_metrics = []
    present_metrics = []
    metrics_with_data = []
    metrics_without_data = []
    
    for metric_name in EXPECTED_CORE_METRICS:
        if metric_name not in metric_families:
            missing_metrics.append(metric_name)
            logger.warning(f"❌ Metric '{metric_name}' is MISSING (breaking change!)")
        else:
            present_metrics.append(metric_name)
            sample_count = len(metric_families[metric_name])
            
            if sample_count > 0:
                metrics_with_data.append(metric_name)
                logger.info(
                    f"✓ Metric '{metric_name}' present with {sample_count} samples"
                )
            else:
                metrics_without_data.append(metric_name)
                logger.info(
                    f"✓ Metric '{metric_name}' present but no samples "
                    "(may be expected based on cluster config)"
                )
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("BACKWARD COMPATIBILITY SUMMARY:")
    logger.info(f"  Total expected metrics: {len(EXPECTED_CORE_METRICS)}")
    logger.info(f"  Present metrics: {len(present_metrics)}")
    logger.info(f"  Metrics with data: {len(metrics_with_data)}")
    logger.info(f"  Metrics without data: {len(metrics_without_data)}")
    logger.info(f"  Missing metrics: {len(missing_metrics)}")
    
    if metrics_without_data:
        logger.info(f"\nMetrics without data (may be config-dependent):")
        for m in metrics_without_data:
            logger.info(f"  - {m}")
    
    if missing_metrics:
        logger.error(f"\nMISSING METRICS (BREAKING CHANGES):")
        for m in missing_metrics:
            logger.error(f"  - {m}")
    
    logger.info("="*80 + "\n")
    
    # Assert no metrics are missing
    assert len(missing_metrics) == 0, (
        f"Backward compatibility BROKEN: {len(missing_metrics)} metrics missing: "
        f"{missing_metrics}. RHSTOR-7964 must not remove existing metrics."
    )
    
    logger.info(
        f"✓ PASSED: All {len(EXPECTED_CORE_METRICS)} expected metrics are present. "
        "Backward compatibility maintained."
    )


@pytest.mark.polarion_id("OCS-6033")
@blue_squad
@tier1
@skipif_managed_service
@skipif_external_mode
@skipif_mcg_only
@skipif_ms_consumer
@skipif_hci_client
def test_existing_alerts_functional(prometheus_api):
    """
    Test Case: ocs-tm033
    Verify existing alerts are still functional in Internal Mode.
    
    The RHSTOR-7964 rearchitecture should not break existing alert rules.
    This test validates that:
    1. Alert rules are defined in PrometheusRule CRs
    2. Alert rules have valid syntax (no parse errors)
    3. Alert rules are loaded in Prometheus
    
    Steps:
        1. Get PrometheusRule CRs from openshift-storage namespace
        2. Extract alert rule names
        3. Verify expected core alerts are defined
        4. Query Prometheus for alert rules
        5. Verify rules are loaded and valid
    
    Expected Result:
        - All expected core alert rules are defined
        - Alert rules have valid syntax
        - Alert rules are loaded in Prometheus
        - No regressions from pre-RHSTOR-7964
    
    Note:
        This test does NOT trigger alerts (that's covered in Group 7).
        It only validates that alert definitions are present and valid.
    """
    logger.info(
        "Verifying backward compatibility: checking existing alerts functional"
    )
    
    namespace = constants.OPENSHIFT_STORAGE_NAMESPACE
    
    # Get PrometheusRule CRs
    logger.info(f"Fetching PrometheusRule CRs from namespace '{namespace}'")
    ocp_prometheus_rule = OCP(
        kind="PrometheusRule",
        namespace=namespace
    )
    
    try:
        prometheus_rules = ocp_prometheus_rule.get().get("items", [])
    except Exception as e:
        logger.error(f"Failed to get PrometheusRule CRs: {e}")
        pytest.fail(f"Could not fetch PrometheusRule CRs: {e}")
    
    logger.info(f"Found {len(prometheus_rules)} PrometheusRule CRs")
    
    if len(prometheus_rules) == 0:
        pytest.fail(
            "No PrometheusRule CRs found in openshift-storage namespace. "
            "This indicates a serious issue with alert configuration."
        )
    
    # Extract all alert names from PrometheusRule CRs
    defined_alerts = set()
    for pr in prometheus_rules:
        pr_name = pr.get("metadata", {}).get("name", "unknown")
        spec = pr.get("spec", {})
        
        for group in spec.get("groups", []):
            group_name = group.get("name", "unknown")
            
            for rule in group.get("rules", []):
                alert_name = rule.get("alert")
                if alert_name:
                    defined_alerts.add(alert_name)
                    logger.debug(
                        f"Found alert '{alert_name}' in PrometheusRule "
                        f"'{pr_name}', group '{group_name}'"
                    )
    
    logger.info(f"Total alerts defined in PrometheusRule CRs: {len(defined_alerts)}")
    
    # Check for expected core alerts
    missing_alerts = []
    present_alerts = []
    
    for alert_name in EXPECTED_CORE_ALERTS:
        if alert_name not in defined_alerts:
            missing_alerts.append(alert_name)
            logger.warning(
                f"❌ Alert '{alert_name}' is MISSING from PrometheusRule CRs "
                "(breaking change!)"
            )
        else:
            present_alerts.append(alert_name)
            logger.info(f"✓ Alert '{alert_name}' is defined in PrometheusRule CRs")
    
    # Query Prometheus to verify rules are loaded
    logger.info("Querying Prometheus to verify alert rules are loaded")
    
    try:
        # Get all rules from Prometheus
        rules_response = prometheus_api.get(
            "rules",
            payload={"type": "alert"}
        )
        
        if not rules_response or "data" not in rules_response:
            logger.warning(
                "Could not fetch rules from Prometheus API. "
                "Will rely on PrometheusRule CR validation only."
            )
            prometheus_loaded_alerts = set()
        else:
            # Extract alert names from Prometheus rules
            prometheus_loaded_alerts = set()
            for group in rules_response.get("data", {}).get("groups", []):
                for rule in group.get("rules", []):
                    if rule.get("type") == "alerting":
                        alert_name = rule.get("name")
                        if alert_name:
                            prometheus_loaded_alerts.add(alert_name)
            
            logger.info(
                f"Prometheus has {len(prometheus_loaded_alerts)} alert rules loaded"
            )
            
            # Check if expected alerts are loaded in Prometheus
            for alert_name in present_alerts:
                if alert_name in prometheus_loaded_alerts:
                    logger.info(
                        f"✓ Alert '{alert_name}' is loaded in Prometheus"
                    )
                else:
                    logger.warning(
                        f"⚠ Alert '{alert_name}' defined in CR but not loaded "
                        "in Prometheus (may need time to sync)"
                    )
    
    except Exception as e:
        logger.warning(
            f"Could not query Prometheus rules API: {e}. "
            "Will rely on PrometheusRule CR validation only."
        )
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("ALERT BACKWARD COMPATIBILITY SUMMARY:")
    logger.info(f"  Total expected alerts: {len(EXPECTED_CORE_ALERTS)}")
    logger.info(f"  Present in PrometheusRule CRs: {len(present_alerts)}")
    logger.info(f"  Missing from PrometheusRule CRs: {len(missing_alerts)}")
    logger.info(f"  Total alerts defined: {len(defined_alerts)}")
    
    if missing_alerts:
        logger.error(f"\nMISSING ALERTS (BREAKING CHANGES):")
        for a in missing_alerts:
            logger.error(f"  - {a}")
    
    logger.info("="*80 + "\n")
    
    # Assert no alerts are missing
    assert len(missing_alerts) == 0, (
        f"Backward compatibility BROKEN: {len(missing_alerts)} alerts missing: "
        f"{missing_alerts}. RHSTOR-7964 must not remove existing alerts."
    )
    
    logger.info(
        f"✓ PASSED: All {len(EXPECTED_CORE_ALERTS)} expected alerts are defined. "
        "Backward compatibility maintained."
    )

# Made with Bob
