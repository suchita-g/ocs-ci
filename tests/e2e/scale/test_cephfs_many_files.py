import subprocess
import logging
import pytest
from tempfile import mkdtemp
from tempfile import mktemp
from shutil import rmtree
import os.path
import uuid
import json
from ocs_ci.ocs import constants, exceptions
from ocs_ci.framework.testlib import E2ETest, ignore_leftovers
from tests import helpers, disruption_helpers
from ocs_ci.framework.pytest_customization.marks import scale
from ocs_ci.utility import utils
from ocs_ci.utility.retry import retry

PVC_NAME = 'cephfs-pvc'
POD_NAME = 'cephfs-test-pod'
DEFAULT_NS = 'default'
TARGET_DIR = '/var/lib/www/html'
TARFILE = 'cephfs.tar.gz'
JSON_FNAME = '/tmp/cephfs1000000.json'
SIZE = '20Gi'
TFILES = 1000000
SAMPLE_TEXT = "A"

log = logging.getLogger(__name__)


def add_million_files():
    """
    Create a directory with one million files in it.
    Tar that directory to a zipped tar file.
    Rsynch that tar file to the cephfs pod
    Extract the tar files on ceph pod onto the mounted ceph filesystem.

    Returns: list of ten of the files created.
    """
    if os.path.isfile(JSON_FNAME):
        os.remove(JSON_FNAME)
    return_list = []
    logging.info(f"Creating {TFILES} files on Cephfs")
    onetenth = TFILES / 10
    endoften = onetenth - 1
    ntar_loc = mkdtemp()
    tarfile = os.path.join(ntar_loc, TARFILE)
    new_dir = mkdtemp()
    for i in range(0, TFILES):
        fname = mktemp(dir=new_dir)
        with open(fname, 'w') as out_file:
            out_file.write(SAMPLE_TEXT)
        if i % onetenth == endoften:
            dispv = i + 1
            logging.info(f'{dispv} local files created')
            return_list.append(fname)
    tmploc = ntar_loc.split('/')[-1]
    subprocess.run([
        'tar',
        'cfz',
        tarfile,
        '-C',
        new_dir,
        '.'
    ])
    subprocess.run([
        'oc',
        '-n',
        DEFAULT_NS,
        'rsync',
        ntar_loc,
        f'{POD_NAME}:{TARGET_DIR}'
    ])
    subprocess.run([
        'oc',
        '-n',
        DEFAULT_NS,
        'exec',
        POD_NAME,
        '--',
        'mkdir',
        f'{TARGET_DIR}/x'
    ])
    subprocess.run([
        'oc',
        '-n',
        DEFAULT_NS,
        'exec',
        POD_NAME,
        '--',
        'tar',
        'xf',
        f'{TARGET_DIR}/{tmploc}/{TARFILE}',
        '-C',
        f'{TARGET_DIR}/x'
    ])
    rmtree(new_dir)
    os.remove(tarfile)
    return return_list


class MillionFilesOnCephfs(object):
    """
    Create pvc and cephfs pod, make sure that the pod is running.
    """
    def __init__(self):
        self.cephfs_pvc = helpers.create_pvc(
            constants.DEFAULT_STORAGECLASS_CEPHFS,
            pvc_name=PVC_NAME,
            namespace=DEFAULT_NS,
            size=SIZE
        )
        self.cephfs_pod = helpers.create_pod(
            interface_type=constants.CEPHFILESYSTEM,
            pvc_name=self.cephfs_pvc.name,
            namespace=DEFAULT_NS,
            node_name='compute-0',
            pod_name=POD_NAME
        )
        helpers.wait_for_resource_state(self.cephfs_pod, "Running", timeout=300)
        logging.info("pvc and cephfs pod created")

    def cleanup(self):
        self.cephfs_pod.delete()
        self.cephfs_pvc.delete()
        logging.info("Teardown complete")


@pytest.fixture(scope='session')
def million_file_cephfs(request):
    million_file_cephfs = MillionFilesOnCephfs()

    def teardown():
        million_file_cephfs.cleanup()
    request.addfinalizer(teardown)


@scale
@ignore_leftovers
@pytest.mark.parametrize(
    argnames=["resource_to_delete", "build_temp"],
    argvalues=[
        pytest.param(
            *['mgr', True],
        ),
        pytest.param(
            *['mon', False],
        ),
        pytest.param(
            *['osd', False],
        ),
        pytest.param(
            *['mds', False],
        ),
    ]
)
class TestMillionCephfsFiles(E2ETest):
    """
    Million cephfs files tester.
    """
    def test_scale_million_cephfs_files(
        self,
        million_file_cephfs,
        resource_to_delete,
        build_temp
    ):
        """
        Add a million files to the ceph filesystem
        Delete each instance of the parametrized ceph pod
        Once the ceph cluster is healthy, verify that no files were lost

        args:
            million_file_cephfs -- fixture
            resource_to_delete (str) -- resource deleted for each testcase
            build_temp -- Add one million files, if True.
        """
        if build_temp:
            self.sample_list = add_million_files()
        else:
            with open(JSON_FNAME, 'r') as fd:
                self.sample_list = json.load(fd)
        proc = subprocess.Popen(
            f'oc -n {DEFAULT_NS} rsh {POD_NAME} df | grep {TARGET_DIR}',
            shell=True,
            stdout=subprocess.PIPE
        )
        dfoutput = proc.communicate()[0]
        logging.info(f"Df results on ceph pod - {dfoutput}")
        if resource_to_delete in ['mgr', 'mon', 'osd', 'mds']:
            logging.info(f"Testing respin of {resource_to_delete}")
            disruption = disruption_helpers.Disruptions()
            disruption.set_resource(resource=resource_to_delete)
            no_of_resources = disruption.resource_count
            for i in range(0, no_of_resources):
                disruption.delete_resource(resource_id=i)
            retry(
                exceptions.CephHealthException,
                tries=60, delay=5, backoff=1
            )(utils.ceph_health_check)()
        logging.info("Verifying that the file count has not changed")
        lsdata = subprocess.Popen([
            'oc',
            '-n',
            DEFAULT_NS,
            'exec',
            POD_NAME,
            '--',
            'ls',
            f'{TARGET_DIR}/x'
        ], stdout=subprocess.PIPE)
        output = subprocess.check_output([
            'wc',
            '-w'
        ], stdin=lsdata.stdout)
        lsdata.wait()
        file_count = int(output)
        assert file_count == TFILES
        logging.info("Testing renaming of files")
        nsample = []
        for sample in self.sample_list:
            parts = sample.split(os.sep)
            newname = str(uuid.uuid4())
            parts[-1] = newname
            fullnew = os.sep.join(parts)
            subprocess.run([
                'oc',
                '-n',
                DEFAULT_NS,
                'exec',
                POD_NAME,
                '--',
                'mv',
                sample,
                fullnew
            ])
            nsample.append(fullnew)
        with open(JSON_FNAME, 'w') as fd:
            json.dump(nsample, fd)
        logging.info("Tests complete")
