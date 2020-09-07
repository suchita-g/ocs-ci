from ocs_ci.ocs import ocp, constants
from ocs_ci.ocs.exceptions import ResourceNotFoundError
from ocs_ci.ocs.uninstall import uninstall_ocs


def test_uninstall():
    """
    Test to check that all OCS resources were removed from cluster

    """
    if ocp.OCP().is_exist('csv'):
        uninstall_ocs()

    # checking for OCS storage classes
    ocs_sc_list = ['ocs-storagecluster-ceph-rbd',
                   'ocs-storagecluster-cephfs',
                   'ocs-storagecluster-ceph-rgw',
                   'openshift-storage.noobaa.io'
                   ]
    sc_obj = ocp.OCP(kind=constants.STORAGECLASS)
    for sc in ocs_sc_list:
        assert sc_obj.is_exist()

    crds = ['backingstores.noobaa.io', 'bucketclasses.noobaa.io', 'cephblockpools.ceph.rook.io',
            'cephfilesystems.ceph.rook.io', 'cephnfses.ceph.rook.io',
            'cephobjectstores.ceph.rook.io', 'cephobjectstoreusers.ceph.rook.io', 'noobaas.noobaa.io',
            'ocsinitializations.ocs.openshift.io', 'storageclusterinitializations.ocs.openshift.io',
            'storageclusters.ocs.openshift.io', 'cephclusters.ceph.rook.io']
    for crd in crds:
        try:
            ocp.OCP.exec_oc_cmd(f'get crd {crd}')
        except ResourceNotFoundError:
            pass
