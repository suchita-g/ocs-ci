# RHSTOR-7964 Test Automation Tracking

## Overview
This document tracks the implementation status of test automation for Epic RHSTOR-7964: "Implement ocs-exporter metrics to work across all deployment models".

**Total Test Cases**: 40 (ocs-tm001 to ocs-tm040)  
**Test Groups**: 16  
**Foundation Branch**: `RHSTOR-7964-tc-00-foundation` ✅ COMPLETED

---

## Implementation Status Summary

| Phase | Groups | Test Cases | Status | Progress |
|-------|--------|------------|--------|----------|
| Phase 1: Foundation & Basic Validation | 1, 4, 12 | 8 TCs | In Progress | 3/8 (37.5%) |
| Phase 2: Core Functionality | 2, 3, 5, 6 | 14 TCs | Not Started | 0/14 (0%) |
| Phase 3: Advanced Features | 7, 8, 9, 10, 11 | 11 TCs | Not Started | 0/11 (0%) |
| Phase 4: Regression & Edge Cases | 13, 14, 15, 16 | 7 TCs | Not Started | 0/7 (0%) |
| **TOTAL** | **16** | **40** | **In Progress** | **3/40 (7.5%)** |

---

## Branch and Test Case Mapping

### Foundation Branch (Common Code)
**Branch**: `RHSTOR-7964-tc-00-foundation`  
**Status**: ✅ COMPLETED  
**Commit**: `8c5f2a1`  
**Files Modified**:
- `ocs_ci/helpers/ocs_metrics_exporter_helpers.py` (30+ new helper functions)

**Helper Functions Added**:
- PVC/Volume operations: `create_test_rbd_pvc()`, `create_test_cephfs_pvc()`, `create_pod_with_pvc()`, `create_snapshot_from_pvc()`, `create_clone_from_snapshot()`
- Ceph toolbox operations: `get_ceph_toolbox_pod()`, `exec_ceph_command()`, `verify_rbd_image_watchers()`, `verify_rbd_children_count()`, `get_ceph_blocklist()`, `add_to_ceph_blocklist()`, `remove_from_ceph_blocklist()`
- Log verification: `verify_no_cli_spawning_in_logs()`, `verify_go_ceph_usage_in_logs()`, `check_for_errors_in_logs()`
- Metric validation: `verify_consumer_name_empty_or_absent()`, `verify_rados_namespace_value()`, `get_metric_value()`, `count_metric_samples()`
- Performance: `measure_pod_memory_usage()`, `measure_scrape_latency()`

---

## Phase 1: Foundation & Basic Validation

### Group 1: Exporter Deployment Verification
**Branch**: `RHSTOR-7964-tc-001-exporter-deployment`  
**Status**: ✅ COMPLETED  
**Commit**: `02a4563`  
**Priority**: P0 (Critical)  
**Test File**: `tests/functional/monitoring/prometheus/metrics/test_ocs_exporter_deployment.py`

| Test Case | Polarion ID | Test Function | Status | Notes |
|-----------|-------------|---------------|--------|-------|
| ocs-tm001 | OCS-6001 | `test_exporter_pod_running()` | ✅ Done | Validates pod running, 1/1 containers, metrics endpoint accessible |
| ocs-tm009 | OCS-6009 | `test_kube_rbac_proxy_removed()` | ✅ Done | Verifies single container, no proxy references in deployment/service/ServiceMonitor |
| ocs-tm010 | OCS-6010 | `test_readiness_endpoint_healthy()` | ✅ Done | Tests /readyz endpoint and readiness probe configuration |

**Key Validations**:
- Pod is running with 1/1 containers ready
- Single container deployment (no kube-rbac-proxy sidecar)
- Successful initialization in logs
- Metrics endpoint accessibility via HTTPS port 8443
- Deployment spec has no proxy references
- Service/ServiceMonitor point directly to exporter
- /readyz endpoint returns healthy status
- Readiness probe configured correctly

**Test Execution**: Works on both internal and provider clusters with runtime mode detection

---

### Group 4: Internal Mode Metrics
**Branch**: `RHSTOR-7964-tc-011-internal-mode-metrics`  
**Status**: 🔄 NOT STARTED  
**Priority**: P0 (Critical)  
**Estimated Effort**: 1.5 days

| Test Case | Polarion ID | Description | Status |
|-----------|-------------|-------------|--------|
| ocs-tm011 | OCS-6011 | Verify consumer_name label empty/absent in internal mode | 📋 Planned |
| ocs-tm012 | OCS-6012 | Verify rados_namespace="openshift-storage" in internal mode | 📋 Planned |
| ocs-tm013 | OCS-6013 | Verify all expected metrics present in internal mode | 📋 Planned |

**Implementation Plan**:
- Single test file with 3 test functions
- Skip on provider/consumer/external modes
- Validate metric labels and values specific to internal mode
- Check rados_namespace correctness
- Verify complete metric set availability

---

### Group 12: Backward Compatibility
**Branch**: `RHSTOR-7964-tc-032-backward-compatibility`  
**Status**: 🔄 NOT STARTED  
**Priority**: P1 (High)  
**Estimated Effort**: 2 days

| Test Case | Polarion ID | Description | Status |
|-----------|-------------|-------------|--------|
| ocs-tm032 | OCS-6032 | Verify existing metrics unchanged (no breaking changes) | 📋 Planned |
| ocs-tm033 | OCS-6033 | Verify existing alerts still functional | 📋 Planned |

**Implementation Plan**:
- Compare metric names/labels before and after
- Validate alert definitions unchanged
- Test alert firing conditions
- Ensure no regression in existing functionality

---

## Phase 2: Core Functionality

### Group 2: go-ceph Migration Validation
**Branch**: `RHSTOR-7964-tc-002-go-ceph-migration`  
**Status**: 🔄 NOT STARTED  
**Priority**: P0 (Critical)  
**Estimated Effort**: 3 days

| Test Case | Polarion ID | Description | Status |
|-----------|-------------|-------------|--------|
| ocs-tm002 | OCS-6002 | Verify no CLI spawning in exporter logs | 📋 Planned |
| ocs-tm003 | OCS-6003 | Verify go-ceph library usage in logs | 📋 Planned |
| ocs-tm004 | OCS-6004 | Verify RBD image watcher count via go-ceph | 📋 Planned |
| ocs-tm005 | OCS-6005 | Verify RBD children count via go-ceph | 📋 Planned |
| ocs-tm006 | OCS-6006 | Verify Ceph blocklist operations via go-ceph | 📋 Planned |

**Implementation Plan**:
- Parse exporter logs for CLI command patterns
- Validate go-ceph library initialization
- Test RBD operations through go-ceph
- Verify blocklist add/remove operations
- Compare results with direct Ceph CLI commands

---

### Group 3: CSI Metadata and PV Caching
**Branch**: `RHSTOR-7964-tc-007-csi-metadata-pv-caching`  
**Status**: 🔄 NOT STARTED  
**Priority**: P0 (Critical)  
**Estimated Effort**: 2.5 days

| Test Case | Polarion ID | Description | Status |
|-----------|-------------|-------------|--------|
| ocs-tm007 | OCS-6007 | Verify CSI OMAP metadata reading | 📋 Planned |
| ocs-tm008 | OCS-6008 | Verify no PV caching (dynamic metadata fetch) | 📋 Planned |

**Implementation Plan**:
- Create PVCs and verify OMAP metadata
- Delete PVCs and verify metadata cleanup
- Test dynamic metadata fetching
- Validate no stale cache issues
- Compare with old PV caching behavior

---

### Group 5: Provider Mode Metrics
**Branch**: `RHSTOR-7964-tc-014-provider-mode-metrics`  
**Status**: 🔄 NOT STARTED (Partial existing implementation)  
**Priority**: P0 (Critical)  
**Estimated Effort**: 2 days

| Test Case | Polarion ID | Description | Status |
|-----------|-------------|-------------|--------|
| ocs-tm014 | OCS-6014 | Verify consumer_name label populated in provider mode | 📋 Planned |
| ocs-tm015 | OCS-6015 | Verify rados_namespace per consumer in provider mode | 📋 Planned |
| ocs-tm016 | OCS-6016 | Verify metrics separated by consumer_name | 📋 Planned |
| ocs-tm017 | OCS-6017 | Verify all expected metrics present in provider mode | 📋 Planned |

**Existing Implementation**:
- Branch: `RHSTOR-7964-consumer_name_label_on_provider_metric`
- Needs review and integration

**Implementation Plan**:
- Review existing branch implementation
- Enhance with additional validations
- Test multi-consumer scenarios
- Verify metric isolation per consumer

---

### Group 6: CephFS Remote Client Tracking
**Branch**: `RHSTOR-7964-tc-018-cephfs-remote-client-tracking`  
**Status**: 🔄 NOT STARTED  
**Priority**: P1 (High)  
**Estimated Effort**: 2 days

| Test Case | Polarion ID | Description | Status |
|-----------|-------------|-------------|--------|
| ocs-tm018 | OCS-6018 | Verify CephFS client tracking on provider | 📋 Planned |
| ocs-tm019 | OCS-6019 | Verify consumer_name in CephFS metrics | 📋 Planned |

**Implementation Plan**:
- Create CephFS PVCs on consumer
- Verify client tracking on provider
- Validate consumer_name label in metrics
- Test multiple consumers

---

## Phase 3: Advanced Features

### Group 7: Alerts Validation
**Branch**: `RHSTOR-7964-tc-020-alerts-validation`  
**Status**: 🔄 NOT STARTED (Partial existing implementation)  
**Priority**: P1 (High)  
**Estimated Effort**: 3 days

| Test Case | Polarion ID | Description | Status |
|-----------|-------------|-------------|--------|
| ocs-tm020 | OCS-6020 | Verify HighRBDCloneSnapshotCount alert | 📋 Planned |
| ocs-tm021 | OCS-6021 | Verify HighCephFSSnapshotCount alert | 📋 Planned |
| ocs-tm022 | OCS-6022 | Verify HighRBDSnapshotCount alert | 📋 Planned |
| ocs-tm023 | OCS-6023 | Verify alert thresholds and firing conditions | 📋 Planned |

**Existing Implementation**:
- Branch: `alert_HIGHRBDCLONESNAPSHOTCOUNT`
- Needs review and integration

**Implementation Plan**:
- Review existing alert test implementation
- Create test scenarios to trigger alerts
- Verify alert firing and resolution
- Test alert labels and annotations

---

### Group 8: Consumer-Side Alerts via gRPC
**Branch**: `RHSTOR-7964-tc-024-consumer-alerts-grpc`  
**Status**: 🔄 NOT STARTED  
**Priority**: P1 (High)  
**Estimated Effort**: 2.5 days

| Test Case | Polarion ID | Description | Status |
|-----------|-------------|-------------|--------|
| ocs-tm024 | OCS-6024 | Verify consumer receives alerts via gRPC | 📋 Planned |
| ocs-tm025 | OCS-6025 | Verify alert propagation latency | 📋 Planned |
| ocs-tm026 | OCS-6026 | Verify alert resolution on consumer | 📋 Planned |

**Implementation Plan**:
- Set up provider-consumer cluster pair
- Trigger alerts on provider
- Verify gRPC alert propagation
- Measure propagation latency
- Test alert resolution flow

---

### Group 9: Multus Network Support
**Branch**: `RHSTOR-7964-tc-027-multus-network-support`  
**Status**: 🔄 NOT STARTED  
**Priority**: P2 (Medium)  
**Estimated Effort**: 2 days

| Test Case | Polarion ID | Description | Status |
|-----------|-------------|-------------|--------|
| ocs-tm027 | OCS-6027 | Verify exporter works with Multus networking | 📋 Planned |
| ocs-tm028 | OCS-6028 | Verify metrics collection over Multus network | 📋 Planned |

**Implementation Plan**:
- Deploy cluster with Multus networking
- Verify exporter pod network configuration
- Test metrics collection over Multus
- Validate network isolation

---

### Group 10: Deployment Tuning
**Branch**: `RHSTOR-7964-tc-029-deployment-tuning`  
**Status**: 🔄 NOT STARTED  
**Priority**: P2 (Medium)  
**Estimated Effort**: 1.5 days

| Test Case | Polarion ID | Description | Status |
|-----------|-------------|-------------|--------|
| ocs-tm029 | OCS-6029 | Verify resource limits and requests | 📋 Planned |
| ocs-tm030 | OCS-6030 | Verify performance under load | 📋 Planned |

**Implementation Plan**:
- Verify resource configuration
- Test memory usage under load
- Measure scrape latency
- Validate performance metrics

---

### Group 11: Dedicated Ceph Credentials
**Branch**: `RHSTOR-7964-tc-031-dedicated-ceph-credentials`  
**Status**: 🔄 NOT STARTED  
**Priority**: P2 (Medium)  
**Estimated Effort**: 1.5 days

| Test Case | Polarion ID | Description | Status |
|-----------|-------------|-------------|--------|
| ocs-tm031 | OCS-6031 | Verify exporter uses dedicated Ceph credentials | 📋 Planned |

**Implementation Plan**:
- Verify dedicated Ceph user creation
- Test credential isolation
- Validate minimal required permissions
- Test credential rotation

---

## Phase 4: Regression & Edge Cases

### Group 13: External Mode Regression
**Branch**: `RHSTOR-7964-tc-034-external-mode-regression`  
**Status**: 🔄 NOT STARTED  
**Priority**: P1 (High)  
**Estimated Effort**: 1.5 days

| Test Case | Polarion ID | Description | Status |
|-----------|-------------|-------------|--------|
| ocs-tm034 | OCS-6034 | Verify exporter works in external mode | 📋 Planned |

**Implementation Plan**:
- Deploy external mode cluster
- Verify exporter functionality
- Test all metrics in external mode
- Ensure no regression

---

### Group 14: Upgrade Testing
**Branch**: `RHSTOR-7964-tc-035-upgrade-testing`  
**Status**: 🔄 NOT STARTED  
**Priority**: P1 (High)  
**Estimated Effort**: 2.5 days

| Test Case | Polarion ID | Description | Status |
|-----------|-------------|-------------|--------|
| ocs-tm035 | OCS-6035 | Verify upgrade from old to new exporter | 📋 Planned |
| ocs-tm036 | OCS-6036 | Verify metrics continuity during upgrade | 📋 Planned |

**Implementation Plan**:
- Test upgrade path from previous version
- Verify no metric data loss
- Test rollback scenario
- Validate upgrade documentation

---

### Group 15: Negative/Error Handling
**Branch**: `RHSTOR-7964-tc-037-negative-error-handling`  
**Status**: 🔄 NOT STARTED  
**Priority**: P2 (Medium)  
**Estimated Effort**: 2 days

| Test Case | Polarion ID | Description | Status |
|-----------|-------------|-------------|--------|
| ocs-tm037 | OCS-6037 | Verify exporter handles Ceph cluster unavailability | 📋 Planned |
| ocs-tm038 | OCS-6038 | Verify exporter handles invalid credentials | 📋 Planned |
| ocs-tm039 | OCS-6039 | Verify exporter recovery after errors | 📋 Planned |

**Implementation Plan**:
- Simulate Ceph cluster failures
- Test invalid credential scenarios
- Verify error logging and recovery
- Test graceful degradation

---

### Group 16: Multi-Consumer Scenarios
**Branch**: `RHSTOR-7964-tc-040-multi-consumer-scenarios`  
**Status**: 🔄 NOT STARTED  
**Priority**: P1 (High)  
**Estimated Effort**: 2 days

| Test Case | Polarion ID | Description | Status |
|-----------|-------------|-------------|--------|
| ocs-tm040 | OCS-6040 | Verify metrics with multiple consumers | 📋 Planned |

**Implementation Plan**:
- Deploy provider with multiple consumers
- Verify metric isolation per consumer
- Test concurrent consumer operations
- Validate consumer_name uniqueness

---

## Git Branch Strategy

### Branch Naming Convention
```
RHSTOR-7964-tc-<group_number>-<context>
```

### Branch Dependencies
1. **Foundation Branch** (`RHSTOR-7964-tc-00-foundation`) - Must be merged first
2. **All other branches** - Can be developed and merged independently

### PR Checklist
- [ ] Branch created from latest main
- [ ] Foundation branch changes included (if needed)
- [ ] All tests pass locally
- [ ] Code follows ocs-ci coding guidelines
- [ ] Proper pytest markers applied
- [ ] Polarion IDs correctly mapped
- [ ] Documentation updated
- [ ] Pre-commit hooks pass
- [ ] Signed-off commits

---

## Testing Guidelines

### Test Markers
All tests should include appropriate markers:
```python
@pytest.mark.polarion_id("OCS-XXXX")
@blue_squad
@tier1  # or @tier2, @tier3
@skipif_managed_service
@skipif_external_mode
@skipif_mcg_only
@skipif_ms_consumer
@skipif_hci_client
```

### Test Execution
Tests should:
- Detect deployment mode at runtime (internal/provider/consumer/external)
- Skip appropriately based on deployment mode
- Clean up resources after execution
- Log detailed information for debugging
- Use helper functions from foundation branch

### Code Reusability
- Common helpers in `ocs_ci/helpers/ocs_metrics_exporter_helpers.py`
- Common constants in `ocs_ci/ocs/constants.py`
- Shared fixtures in test conftest.py files

---

## Progress Tracking

### Completed (3/40 - 7.5%)
- ✅ Foundation branch with 30+ helper functions
- ✅ Group 1: Exporter deployment verification (3 TCs)

### In Progress (0/40 - 0%)
- None currently

### Next Priority (5 TCs)
1. Group 4: Internal mode metrics (3 TCs) - P0
2. Group 12: Backward compatibility (2 TCs) - P1

### Remaining (32/40 - 80%)
- Phase 2: Core Functionality (14 TCs)
- Phase 3: Advanced Features (11 TCs)
- Phase 4: Regression & Edge Cases (7 TCs)

---

## Estimated Timeline

| Phase | Groups | Test Cases | Effort (days) | Status |
|-------|--------|------------|---------------|--------|
| Foundation | 0 | N/A | 2 | ✅ Done |
| Phase 1 | 1, 4, 12 | 8 | 5 | 37.5% Done |
| Phase 2 | 2, 3, 5, 6 | 14 | 9.5 | Not Started |
| Phase 3 | 7, 8, 9, 10, 11 | 11 | 11.5 | Not Started |
| Phase 4 | 13, 14, 15, 16 | 7 | 8 | Not Started |
| **TOTAL** | **16** | **40** | **36** | **7.5% Done** |

**Note**: Timeline assumes sequential implementation. Parallel development by multiple engineers can reduce overall time.

---

## References

- **Epic**: RHSTOR-7964
- **Test Plan**: `/Users/suchita/Documents/ODF/RHSTOR DOCs/RHSTOR-7964_Final_testplan.xlsx`
- **Design Doc**: `/Users/suchita/Documents/ODF/RHSTOR DOCs/OCS Metrics Exporter - Google Docs`
- **Coding Guidelines**: https://ocs-ci.readthedocs.io/en/latest/getting_started.html
- **Earlier Analysis**: `file:///Users/suchita/workdir/ProjectAbellAutomation/abell-tracking/RHSTOR-7964_Automation_Test_Plan.html`

---

## Notes

### Key Architecture Changes in RHSTOR-7964
1. **Single Container Deployment**: Removed kube-rbac-proxy sidecar
2. **go-ceph Library**: No CLI spawning for Ceph operations
3. **CSI OMAP Metadata**: Dynamic metadata reading, no PV caching
4. **consumer_name Label**: Multi-tenant metric isolation
5. **/readyz Endpoint**: Health check endpoint
6. **HTTPS Port 8443**: TLS-enabled metrics endpoint

### Testing Considerations
- Tests must work across all deployment models (internal, provider, consumer, external)
- Runtime mode detection preferred over parameterization
- Proper resource cleanup essential
- Detailed logging for debugging
- Performance testing under load

---

**Last Updated**: 2026-05-25  
**Document Version**: 1.0  
**Maintained By**: QA Automation Team