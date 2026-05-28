# Regression Analysis: test_reboot_on_tainted_node

## Quick answers

| Question | Answer |
|----------|--------|
| **1. Automation or product issue?** | **Likely automation (timing)**. Inconsistent failure and failure at `wait_for_pods_to_be_running` after taint/toleration point to variable operator rollout; no retry in older code caused a single slow reconciliation to fail the test. Product is only clearly at fault if must-gather shows pods permanently Pending due to missing/wrong toleration. |
| **2. What does the test do?** | See §2 below. In short: apply custom taint + tolerations → wait for pods → check subscription/pod tolerations → reboot one ODF node → verify pods and cluster health. |
| **3. If automation: root cause and solution?** | **Root cause:** No retry around first `wait_for_pods_to_be_running` (in older code), and order differed from sibling test. **Solution:** Align order (sleep then wait then check subscriptions), add retry (3 tries, 60 s delay) around first wait, and add failure diagnostics (log non-running pods). |

---

## 1. Automation vs Product Issue

**Conclusion: Likely an automation (timing) issue**, with a possible product component if pods remain Pending due to toleration/placement.

- **Inconsistent failure** points to timing/race: the same steps sometimes succeed within the allowed time and sometimes do not.
- The assertion fails at **wait_for_pods_to_be_running(timeout=900, sleep=15)** after applying taints/tolerations and a fixed **sleep(300)**. No retry is used, so a single slow rollout or delayed reconciliation can cause a failure.
- To confirm product: from must-gather, check **which pods were not Running** and their **reason** (e.g. Pending + "0/X nodes available: node(s) had untolerated taint" → product/scheduler; ImagePullBackOff → env; ContainerCreating for a long time → timing/automation).

---

## 2. What the Test Does

**test_reboot_on_tainted_node** (OCS-5985) does the following:

1. **Taint ODF nodes** with a custom taint (`xyz=true:NoSchedule`) and **set tolerations** on:
   - StorageCluster (placement)
   - Subscriptions (ODF operator)
   - (Pre-4.16) OCSInitialization, configmap; (4.19+) CSI Drivers
2. **Check** that tolerations appear on all **subscription** specs (`check_toleration_on_subscriptions`).
3. **Wait** 300 seconds for pods to respin with the new tolerations.
4. **Assert** all relevant pods in `openshift-storage` are Running within 900 seconds (**failure point**).
5. **Check** that all ODF pods have the custom toleration (`check_toleration_on_pods`).
6. **Reboot** one random ODF node (non-blocking), wait for node Ready, cluster connectivity, and nodes status.
7. **Assert** again that all pods are Running, verify tolerations on pods, and run sanity health check.

So the test validates: custom taint + tolerations → subscriptions and pods get the toleration → after a node reboot, pods (including on the rebooted node) stay Running and healthy.

---

## 3. Root Cause (Automation) and Solution

### Root cause

- **Order difference vs the similar test:** In **test_non_ocs_taint_and_tolerations** the sequence is:
  `apply_custom_taint_and_toleration()` → **sleep(300)** → **wait_for_pods_to_be_running(900)** → **then** `check_toleration_on_subscriptions()`.
  In **test_reboot_on_tainted_node** it is:
  `apply_custom_taint_and_toleration()` → **check_toleration_on_subscriptions()** → **sleep(300)** → **wait_for_pods_to_be_running(900)**.

- **check_toleration_on_subscriptions** only verifies that Subscription CR specs contain the toleration; it does **not** wait for operators to reconcile or for new pods to be created and scheduled. So the “settling” behavior is the same (300s + 900s), but the reboot test explicitly checks subscription spec first, which doesn’t guarantee that pod rollout has started or finished.

- **No retry:** `wait_for_pods_to_be_running` is called once. After taint/toleration changes, operator reconciliation and rollouts can be variable (image pulls, multiple deployments rolling). One transient non-Running state within the 900s window causes a hard failure.

- **Single timeout:** If the first 900s run hits a moment where one or more pods are still ContainerCreating or Pending, the test fails even if they would have been Running shortly after.

So the failure is driven by **automation timing and lack of resilience** (no retry, strict order), not necessarily by a product bug. Product is only clearly at fault if must-gather shows pods permanently Pending due to missing/wrong toleration or placement.

### Recommended automation changes

1. **Align order with test_non_ocs_taint_and_tolerations**
   In **test_reboot_on_tainted_node**, do:
   - `apply_custom_taint_and_toleration()`
   - **sleep(300)**
   - **wait_for_pods_to_be_running(timeout=900, sleep=15)**
   - **then** `check_toleration_on_subscriptions(toleration_key="xyz")`
   This gives the cluster the same “settle then assert” behavior as the other test and avoids asserting pod state before operators have had time to roll out.

2. **Add retry around the first wait_for_pods_to_be_running**
   Wrap the first `wait_for_pods_to_be_running` (after taint/toleration) in a retry (e.g. 2–3 tries, 60–120 s delay) so a single slow rollout doesn’t fail the test.

3. **Optional: improve failure diagnostics**
   On assertion failure, log or collect which pods were not Running and their status (e.g. by calling `check_pods_in_running_state` or equivalent and logging the result) so that next failures can be classified as timing vs product (e.g. Pending with “untolerated taint”).

Implementing (1) and (2) in the test is the proposed fix; (3) helps with future triage.

---

## 4. Must-gather review (ocs_must_gather (6).tar.gz)

**Pod status (openshift-storage):**

- **Pending pods:** At least **3** pods in `openshift-storage` were in **Pending** at gather time:
  1. **ip-10-0-94-227us-east-2computeinternal-debug-m28s9** – debug pod (no `nodeName` in one snapshot; expected for debug).
  2. **rook-ceph-mon-a-865b8fc9d8-bwvgk** (from events) – condition: `0/10 nodes are available: 3 node(s) didn't match PersistentVolume's node affinity, 3 node(s) didn't match Pod's node affinity/selector, **4 node(s) had untolerated taint(s)**. no new claims to deallocate, preemption: 0/10 nodes are available: 10 Preemption is not helpful for scheduling.'
  3. **rook-ceph-osd-1-85f54958c8-ldpsr** (from events) – `0/10 nodes are available: **4 node(s) had untolerated taint(s)**, 6 node(s) didn't match Pod's node affinity/selector. no new claims to deallocate, preemption: 0/10 nodes are available: 10 Preemption is not helpful for scheduling.'
  4. At least one **rook-ceph-osd-*** pod (ocs-deviceset-1-data-0bdkht) in the pods list has **phase: Pending** with the same condition: `0/10 nodes are available: **4 node(s) had untolerated taint(s)**, 6 node(s) didn't match Pod's node affinity/selector. no new claims to deallocate, preemption: 0/10 nodes are available: 10 Preemption is not helpful for scheduling.'

**Events (openshift-storage):**

- Multiple **FailedScheduling** events with reason **Untolerated taint**:
  - Messages like: `0/10 nodes are available: 4 node(s) had untolerated taint(s), 6 node(s) didn't match Pod's node affinity/selector. no new claims to deallocate, preemption: 0/10 nodes are available: 10 Preemption is not helpful for scheduling.'
  - Affected pods include: **rook-ceph-mon-a-865b8fc9d8-bwvgk**, **rook-ceph-osd-1-85f54958c8-ldpsr**, and other OSD/mon pods.
- **taint-eviction-controller** events are also present (expected when nodes are tainted).

**Conclusion from must-gather:**

- **Pods are Pending with events explicitly stating “node(s) had untolerated taint(s)”.**
  So at least part of the failure is **product/placement-related**: some ODF pods (Ceph mon, Ceph OSD) did not have the custom **xyz** toleration at the time of the failure. Either:
  - The StorageCluster placement (with xyz toleration) had not been applied to those components, or
  - The operator had not yet rolled out new pod templates with the toleration (timing/rollout), so the test’s single 900 s wait was not enough for all deployments to roll out.
- The Pending OSD pod in the dump has only the default OSD tolerations (e.g. `node.ocs.openshift.io/storage`, `node.kubernetes.io/not-ready`) and **no xyz toleration**, which matches “4 node(s) had untolerated taint(s)”.

**Verdict:** The must-gather supports **both**:
1. **Product/placement:** Some ODF workloads were unschedulable due to **untolerated taint** (custom taint not reflected on those pods).
2. **Automation/timing:** Retrying the “pods running” check (and optionally giving more time for rollout) would reduce flakiness when the operator is slow to propagate the new toleration to all deployments.
