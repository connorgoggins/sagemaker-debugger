import json
import tensorflow as tf

from enum import Enum


class TFDistributionStrategy(Enum):
    NONE = 0
    HOROVOD = 1
    MIRRORED_STRATEGY = 2
    PARAMETER_SERVER_STRATEGY = 3


def node_name(n):
    if n.startswith("^"):
        return n[1:]
    else:
        return n.split(":")[0]


def extract_graph_summary(graph_def):
    """Extracts useful information from the graph and returns them."""
    name_to_input_name = {}  # Keyed by the dest node name.
    name_to_node = {}  # Keyed by node name.

    # Keeps track of node sequences. It is important to still output the
    # operations in the original order.
    name_to_seq_num = {}  # Keyed by node name.
    seq = 0
    for node in graph_def.node:
        n = node_name(node.name)
        name_to_node[n] = node
        name_to_input_name[n] = [node_name(x) for x in node.input]
        name_to_seq_num[n] = seq
        seq += 1
    return name_to_input_name, name_to_node, name_to_seq_num


def get_original_fetch_ops(fetches):
    if isinstance(fetches, tf.Tensor) or isinstance(fetches, tf.Variable):
        return [fetches.op]
    elif isinstance(fetches, tf.Operation):
        return [fetches]
    elif isinstance(fetches, list):
        rval = []
        for f in fetches:
            rval.extend(get_original_fetch_ops(f))
        return rval
    elif isinstance(fetches, dict):
        rval = []
        for key in fetches:
            rval += get_original_fetch_ops(fetches[key])
        return rval
    else:
        raise RuntimeError("Invalid fetches")


""""
The TF_CONFIG environment variable is the standard way to specify the cluster configuration
to each worker that is part of the cluster.


Given below some examples of TF_CONFIG:


  Example of `TF_CONFIG` for chief training worker (must have one and only one):

  Note that the chief worker also does the model training job, similar to other
  non-chief training workers (see next paragraph). In addition to the model
  training, it manages some extra work, e.g., checkpoint saving and restoring,
  writing summaries, etc.

  TF_CONFIG='{
      "cluster": {
          "chief": ["host0:2222"],
          "worker": ["host1:2222", "host2:2222", "host3:2222"],
          "ps": ["host4:2222", "host5:2222"]
      },
      "task": {"type": "chief", "index": 0}
  }'


  Example of `TF_CONFIG` for non-chief training worker (optional, could be
  multiple):

  TF_CONFIG='{
      "cluster": {
          "chief": ["host0:2222"],
          "worker": ["host1:2222", "host2:2222", "host3:2222"],
          "ps": ["host4:2222", "host5:2222"]
      },
      "task": {"type": "worker", "index": 0}
  }'

  where the `task.index` should be set as 0, 1, 2, in this example, respectively
  for non-chief training workers.


  Example of `TF_CONFIG` for parameter server, aka ps (could be multiple):

  TF_CONFIG='{
      "cluster": {
          "chief": ["host0:2222"],
          "worker": ["host1:2222", "host2:2222", "host3:2222"],
          "ps": ["host4:2222", "host5:2222"]
      },
      "task": {"type": "ps", "index": 0}
  }'

  where the `task.index` should be set as 0 and 1, in this example, respectively
  for parameter servers.

  Example of `TF_CONFIG` for evaluator task. Evaluator is a special task that is
  not part of the training cluster. There could be only one. It is used for
  model evaluation.

  TF_CONFIG='{
      "cluster": {

          "chief": ["host0:2222"],
          "worker": ["host1:2222", "host2:2222", "host3:2222"],
          "ps": ["host4:2222", "host5:2222"]
      },
      "task": {"type": "evaluator", "index": 0}
  }'

  NOTE: If the "chief" is missing in TF_CONFIG["cluster"], the worker with index 0 assumes this role.

See https://www.tensorflow.org/guide/distributed_training#setting_up_tf_config_environment_variable
"""


def is_parameter_server_strategy(tf_config: str) -> bool:
    try:
        tf_config = json.loads(tf_config)
    except json.JSONDecodeError:
        return False  # Do not break for incorrectly set tf_config
    return "cluster" in tf_config and "ps" in tf_config["cluster"]


def get_worker_id_from_tf_config(tf_config: str) -> str:
    """Valid roles in a cluster is "chief", "worker", "ps" and "evaluator"."""
    tf_config = json.loads(tf_config)
    task = tf_config["task"]
    worker_type = task["type"]
    worker_index = task["index"]
    return f"{worker_type}_{worker_index}"


def get_num_workers_from_tf_config(tf_config: str) -> int:
    tf_config = json.loads(tf_config)
    workers = tf_config["cluster"]["worker"]
    if "chief" in tf_config["cluster"]:
        workers.extend(tf_config["cluster"]["chief"])
    return len(workers)
