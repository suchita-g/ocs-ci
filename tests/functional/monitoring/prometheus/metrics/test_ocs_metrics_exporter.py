# -*- coding: utf8 -*-
"""
RHSTOR-7964: ocs-metrics-exporter baseline checks on clusters where the workload is deployed.

Covers internal/provider-style topology: Deployment present, single ready pod, single container
(no kube-rbac-proxy sidecar), and Prometheus text exposition on /metrics.

Metrics scrape matches manual QE: for TLS listeners (e.g. 8443), uses
``oc create token prometheus-k8s -n openshift-monitoring`` and
``curl -sk -H 'Authorization: Bearer …' https://127.0.0.1:8443/metrics`` from inside the exporter pod.
When multicluster includes a consumer, asserts ``consumer_name`` appears in the metrics body
(equivalent to ``| grep consumer_name``).
"""

import logging

import pytest

from ocs_ci.framework import config
from ocs_ci.framework.pytest_customization.marks import (
    blue_squad,
    skipif_external_mode,
    skipif_hci_client,
    skipif_mcg_only,
    skipif_ms_consumer,
    runs_on_provider,
)
from ocs_ci.framework.testlib import skipif_managed_service, tier1
from ocs_ci.helpers import ocs_metrics_exporter_helpers as ome_helpers
from ocs_ci.ocs import constants
from ocs_ci.ocs.ocp import OCP
from ocs_ci.ocs.resources.pod import get_pods_having_label


logger = logging.getLogger(__name__)


@blue_squad
@tier1
@skipif_managed_service
@skipif_external_mode
@skipif_mcg_only
@skipif_ms_consumer
@skipif_hci_client
@runs_on_provider
def test_ocs_metrics_exporter_deployment_pod_and_metrics_endpoint():
    """
    Verify ocs-metrics-exporter (RHSTOR-7964 internal baseline):

        * Deployment exists with desired replicas available
        * One pod Running with READY 1/1
        * Single container, no kube-rbac-proxy
        * GET /metrics returns Prometheus text format (HTTPS + bearer token when endpoint requires it)
        * With consumer topology: metrics body includes consumer_name

    Skips cleanly when the workload is not installed (e.g. topology without exporter).

    Polarion: assign a case ID when publishing (RHSTOR-7964).
    """
    namespace = config.ENV_DATA["cluster_namespace"]
    deploy_items = ome_helpers.get_ocs_metrics_exporter_deployments(namespace)
    if not deploy_items:
        pytest.skip(
            "ocs-metrics-exporter Deployment not found (not deployed on this topology / version)"
        )

    assert len(deploy_items) == 1, (
        "expected exactly one ocs-metrics-exporter Deployment, "
        f"found {len(deploy_items)}"
    )
    deployment = deploy_items[0]
    deploy_name = deployment["metadata"]["name"]
    spec_replicas = deployment.get("spec", {}).get("replicas", 1)
    status = deployment.get("status", {}) or {}
    ready = status.get("readyReplicas", 0) or 0
    available = status.get("availableReplicas", 0) or 0
    logger.info(
        "Deployment %s/%s replicas spec=%s ready=%s available=%s",
        namespace,
        deploy_name,
        spec_replicas,
        ready,
        available,
    )
    assert ready == spec_replicas and available == spec_replicas, (
        f"Deployment {deploy_name} must have readyReplicas and availableReplicas "
        f"matching spec.replicas={spec_replicas}; status={status!r}"
    )

    ocp_pod = OCP(kind=constants.POD, namespace=namespace)
    assert ocp_pod.wait_for_resource(
        condition=constants.STATUS_RUNNING,
        selector=constants.OCS_METRICS_EXPORTER,
        resource_count=1,
        timeout=300,
    ), "ocs-metrics-exporter pod did not reach Running in time"

    all_items = get_pods_having_label(
        constants.OCS_METRICS_EXPORTER, namespace=namespace
    )
    running_items = [
        p
        for p in all_items
        if p.get("status", {}).get("phase") == constants.STATUS_RUNNING
    ]
    assert (
        len(running_items) == 1
    ), f"expected exactly one Running ocs-metrics-exporter pod, found {len(running_items)}"

    pod_name = running_items[0]["metadata"]["name"]
    ready_col = ocp_pod.get_resource(pod_name, "READY")
    assert (
        ready_col == "1/1"
    ), f"pod {pod_name} must be 1/1 Ready for single-container exporter; got READY={ready_col!r}"

    metrics_pod = ome_helpers.get_ocs_metrics_exporter_pod(namespace)
    assert metrics_pod is not None, "Running ocs-metrics-exporter pod not found"
    ome_helpers.assert_single_exporter_container_without_rbac_proxy(metrics_pod)

    metrics_body = ome_helpers.scrape_metrics_text_sample(metrics_pod)
    logger.info("/metrics sample (first 500 chars): %s", metrics_body[:500])
    ome_helpers.assert_prometheus_exposition_text(metrics_body)
    if ome_helpers.should_expect_consumer_name_in_metrics():
        ome_helpers.assert_consumer_name_in_metrics(metrics_body)
