import logging
import pytest

from ocs_ci.ocs.bucket_utils import (
    copy_objects,
    craft_s3_command,
    sync_object_directory,
    list_objects_from_bucket,
    gen_empty_file_and_upload,
)
from ocs_ci.framework.pytest_customization.marks import orange_squad, mcg
from ocs_ci.framework.testlib import E2ETest
from ocs_ci.framework.pytest_customization.marks import (
    scale,
    skipif_ocs_version,
    jira,
)
from ocs_ci.ocs.resources.mcg import MCG


log = logging.getLogger(__name__)


@mcg
@orange_squad
@scale
class TestListOfObjects(E2ETest):
    """
    Test to verify the list whole objects without any failures

    """

    @skipif_ocs_version("<4.8")
    @pytest.mark.polarion_id("OCS-3926")
    def test_list_large_number_of_objects(
        self,
        fedora_pod_session,
        bucket_factory,
    ):
        """
        Testcase to verify list whole objects lists without any failures

        1. Create a OBC
        2. Copied/Uploaded directory to the objects which
           contains large number of directories, for e,g linux tar
        3. List objects

        """

        # Create OBC
        bucketname = bucket_factory(1)[0].name
        full_object_path = f"s3://{bucketname}"
        s3_obj = MCG(bucketname)

        # Get linux tar and copy linux directory to the objects
        data_dir = "/home/linux_tar_dir/"
        files_count = fedora_pod_session.exec_sh_cmd_on_pod(
            command=f"find  {data_dir} -type f -follow -print | wc -l", sh="sh"
        )

        copy_objects(
            fedora_pod_session,
            data_dir,
            full_object_path,
            s3_obj,
            recursive=True,
            timeout=9000,
        )

        # List the objects recursively
        log.info("List objects recursively")
        file_name = "/tmp/list_object"
        cmd = f"ls {full_object_path} --recursive >> {file_name}"
        fedora_pod_session.exec_cmd_on_pod(
            command=craft_s3_command(cmd=cmd, mcg_obj=s3_obj),
            out_yaml_format=False,
            timeout=9000,
        )

        # Verify when listing any errors found
        log.info("Verify when listing objects recursively found any Timeout error")
        err_msg = (
            "'An error occurred (504) when calling the ListObjectsV2 "
            "operation (reached max retries: 2): Gateway Timeout'"
        )
        cmd = f"grep {err_msg} {file_name}"
        command_output = fedora_pod_session.exec_cmd_on_pod(
            command=cmd, out_yaml_format=False, timeout=600
        )
        log.info(command_output)
        assert not command_output, "Error: Results found for grep command"

        # Verify for any errors found
        log.info("Verify when listing objects recursively found any Errors")
        cmd = f"grep -i 'An error occurred' {file_name}"
        command_output = fedora_pod_session.exec_cmd_on_pod(
            command=cmd, out_yaml_format=False, timeout=600
        )
        log.info(command_output)
        assert not command_output, "Error: Results found for grep command"

        # ToDO: Copy the list objects file (i.e /tmp/list_object)
        #  to ocs-ci logs which helps on debugging

        cmd = f"grep -c 'linux' {file_name}"
        objects_count = fedora_pod_session.exec_cmd_on_pod(
            command=cmd, out_yaml_format=False, timeout=600
        )
        assert files_count == objects_count, (
            f"Files count {files_count} and objects_count {objects_count} does not match. "
            "Check does all objects are listed correctly!!!"
        )

    @skipif_ocs_version("<4.9")
    @pytest.mark.polarion_id("OCS-4650")
    def test_list_with_prefix_delimiter(self, bucket_factory, scale_cli_pod, mcg_obj):
        """
        This will test list directory with large number of objects using prefix & delimeter
        """
        origin_dir, large_dir = ("large_objects", "dir_500")
        bucketclass = {
            "interface": "OC",
            "backingstore_dict": {"aws": [(1, "eu-central-1")]},
        }
        bucket_name = bucket_factory(bucketclass=bucketclass)[0].name

        # sync all the directories and objects to the bucket
        sync_object_directory(
            scale_cli_pod,
            f"{origin_dir}",
            f"s3://{bucket_name}",
            s3_obj=mcg_obj,
            timeout=27000,
        )
        log.info("Synced all the object directories!")

        # list all directories first
        try:
            list_objects_from_bucket(
                scale_cli_pod,
                f"s3://{bucket_name}",
                s3_obj=mcg_obj,
            )
        except Exception as ex:
            if "Timeout" in ex.args[0]:
                log.error(f"Failed with: {ex.args[0]}")
            raise ex

        # list objects with prefix and delimeter
        list_objects_from_bucket(
            scale_cli_pod,
            f"s3://{bucket_name}",
            prefix=f"{large_dir}",
            s3_obj=mcg_obj,
            timeout=9000,
        )
        log.info("Test succeeded without any errors!")

    @jira("DFBUGS-1123")
    @pytest.mark.polarion_id("OCS-6095")
    def test_list_objects_single_dir(
        self,
        scale_noobaa_resources_session,
        bucket_factory,
        awscli_pod_session,
        mcg_obj_session,
        test_directory_setup,
    ):
        """
        Test list objects from a single directory when it has millions of
        objects

        """

        # create the bucket
        bucket = bucket_factory()[0]
        log.info(f"Created bucket {bucket.name}")

        # generate 1 million empty file objects and upload
        # to the bucket parallely under the prefix
        prefix = "single_dir"
        gen_empty_file_and_upload(
            mcg_obj_session,
            awscli_pod_session,
            test_directory_setup.origin_dir,
            amount=1000000,
            bucket=bucket.name,
            prefix=prefix,
            threads=10,
            timeout=10800,
        )
        log.info(f"Uploaded objects to the bucket {bucket.name}")

        # list objects directly from the bucket using just the delimiter
        list_objects_from_bucket(
            pod_obj=awscli_pod_session,
            target=f"s3://{bucket.name}/",
            s3_obj=mcg_obj_session,
            timeout=60,
        )
        log.info("List objects using delimiter was successful without any issues")

        # list objects from the bucket using prefix and delimiter
        list_objects_from_bucket(
            pod_obj=awscli_pod_session,
            target=f"s3://{bucket.name}",
            prefix=prefix,
            s3_obj=mcg_obj_session,
            timeout=60,
        )
        log.info(
            "List objects using prefix and delimter was successful without any issues"
        )
