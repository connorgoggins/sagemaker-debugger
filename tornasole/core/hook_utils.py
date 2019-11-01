import os

from .json_config import DEFAULT_SAGEMAKER_TORNASOLE_PATH
from .sagemaker_utils import is_sagemaker_job, get_sagemaker_out_dir
from .utils import is_s3
from .logger import get_logger
from .access_layer.utils import check_dir_exists

logger = get_logger()


def verify_and_get_out_dir(out_dir):
    if is_sagemaker_job():
        if out_dir is not None:
            logger.warning(
                "The out_dir parameter was set but job is running in a "
                "SageMaker environment, hence it is being ignored. "
                "Writing tensors to "
                "{}".format(DEFAULT_SAGEMAKER_TORNASOLE_PATH)
            )
        out_dir = get_sagemaker_out_dir()
        # here we don't check whether the directory exists because
        # sagemaker creates the directory and it will exist.
        # sagemaker assures us that this directory is unique for each job
        # so there is no chance of tensors from two jobs being merged
    else:
        if out_dir is None:
            raise RuntimeError(
                "out_dir is a required argument when " "running outside of SageMaker environments"
            )
        is_s3_path, _, _ = is_s3(out_dir)
        if not is_s3_path:
            out_dir = os.path.expanduser(out_dir)
        # we check and raise error if directory already exists because
        # we don't want to merge tensors from current job with
        # tensors from previous job
        check_dir_exists(out_dir)

    return out_dir
