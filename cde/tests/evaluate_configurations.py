import itertools
import multiprocessing
import pandas as pd
import numpy as np
import gc

from contextlib import contextmanager
from cde.density_estimator import LSConditionalDensityEstimation, KernelMixtureNetwork
from cde.density_simulation import EconDensity, GaussianMixture
from cde.evaluation.GoodnessOfFit import GoodnessOfFit
from cde.utils import io
from multiprocessing import Pool



def prepare_configurations():
  #
  # """ configurations """
  # estimator_params = {'KMN': tuple(itertools.product(["agglomerative", "k_means", "random"],  # center_sampling_method
  #   [20, 50],  # n_centers
  #   [True, False],  # keep_edges
  #   [0.1, 1, 2],  # init_scales
  #   [None],  # estimator
  #   [None],  # X_ph
  #   [True],  # train_scales
  #   [20],  # n training epochs
  #   [0.1, 1., 2.],  # x_noise_std
  #   [0.1, 1., 2.])),  # y_noise_std
  #   'LSCDE': tuple(itertools.product(['k_means'],  # center_sampling_method
  #     [0.1, 0.2, 1.],  # bandwidth
  #     [20, 50],  # n_centers
  #     [0.1, 0.4, 1.],  # regularization
  #     [False, True]))}  # keep_edges}
  #
  # simulators_params = {
  #     'Econ': tuple([0]),  # std
  #     'GMM': (30, 1, 1, 4.5)  # n_kernels, ndim_x, ndim_y, means_std
  # }


  """ configurations """
  estimator_params = {'KMN': tuple(itertools.product(["agglomerative", "k_means", "random"],  # center_sampling_method
    [20, 50],  # n_centers
    [True],  # keep_edges
    [[0.1]],  # init_scales
    [None],  # estimator
    [None],  # X_ph
    [True],  # train_scales
    [20],  # n training epochs
    [0.1],  # x_noise_std
    [0.1]))}  # keep_edges}

  simulators_params = {
      'GMM': (30, 1, 1, 4.5)  # n_kernels, ndim_x, ndim_y, means_std
  }



  """ object references """
  estimator_references = {'KMN': KernelMixtureNetwork, 'LSCDE': LSConditionalDensityEstimation, }
  simulator_references = { 'Econ': EconDensity, 'GMM': GaussianMixture}

  """ estimators """
  configured_estimators = [estimator_references[estimator](*config) for estimator, est_params in estimator_params.items() for config in est_params]

  """ simulators """
  configured_simulators = [simulator_references[simulator](*sim_params) for simulator, sim_params in simulators_params.items()]

  return configured_estimators, configured_simulators



def create_configurations(configured_estimators, configured_simulators, n_observations=10**4):
  """
  creates all possible combinations from the (configured) estimators and simulators.
    Args:
      configured_estimators: a list instantiated estimator objects with length n while n being the number of configured estimators
      configured_simulators: a list instantiated simulator objects with length n while m being the number of configured simulators
      n_observations: either a list or a scalar value that defines the number of observations from the simulation model that are used to train the estimators

    Returns:
      if n_observations is not a list, a list containing n*m=k tuples while k being the number of the cartesian product of estimators and simulators is
      returned --> shape of tuples: (estimator object, simulator object)
      if n_observations is a list, n*m*o=k while o is the number of elements in n_observatons list
  """
  if not np.isscalar(n_observations):
    return [(estimator, simulator, n_obs) for estimator, simulator, n_obs in itertools.product(configured_estimators, configured_simulators, n_observations)]
  else:
    return [(estimator, simulator, n_observations) for estimator, simulator in itertools.product(configured_estimators, configured_simulators)]


def run_configurations(tasks, output_dir="./", prefix_filename=None, estimator_filter=None, parallelized=False, limit=None):
  """
  Runs the given configurations, i.e.
  1) fits the estimator to the simulation and
  2) executes goodness-of-fit (currently: e.g. kl-divergence, wasserstein-distance etc.) tests
  Every successful run yields a result object of type GoodnessOfFitResult which contains information on both estimator, simulator and chosen hyperparameters
  such as n_samples, see GoodnessOfFitResult documentation for more information.

    Args:
      tasks: a list containing k tuples, each tuple has the shape (estimator object, simulator object)
      estimator_filter: a parameter to decide whether to execute just a specific type of estimator, e.g. "KernelMixtureNetwork",
                        must be one of the density estimator class types
      limit: limit the number of (potentially filtered) tasks
      parallelized: if True, the configurations are run in parallel mode on all available cpu's

    Returns:
       a list of GoodnessOfFitResults objects (one per configuration run) and a list of the GoodnessOfFit objects (one per configuration run)
      which contain the fitted estimators
  """
  assert len(tasks) > 0
  if estimator_filter is not None:
    tasks = [tupl for tupl in tasks if estimator_filter in tupl[0].__class__.__name__]
  assert len(tasks), "no tasks to execute after filtering for the estimator"
  print("Running configurations. Number of total tasks: ", len(tasks))

  if limit is not None:
    assert limit > 0, "limit mustn't be negative"
  else:
    limit = len(tasks)

  config_file_name = "configurations"
  result_file_name = "result"
  if prefix_filename is not None:
    config_file_name = prefix_filename + "_" + config_file_name + "_"
    result_file_name = prefix_filename + "_" + result_file_name + "_"

  if parallelized:
    # todo: come up with a work-around for nested parallelized loops and tensorflow non-pickable objects
    with poolcontext(processes=None) as pool:
      gof_objects, gof_results = pool.starmap(run_single_configuration, tasks[:limit])
      return gof_objects, gof_results

  else:
    file_configurations = io.get_full_path(output_dir=output_dir, suffix=".pickle", file_name=config_file_name)
    file_results = io.get_full_path(output_dir=output_dir, suffix=".csv", file_name=result_file_name)
    with open(file_configurations, "a+b") as file_handle_configs, open(file_results, "a") as file_handle_results:
      for i, task in enumerate(tasks[:limit]):
        try:
          print("running task:", i+1, "Estimator:", task[0].__class__.__name__, " Simulator: ", task[1].__class__.__name__)
          gof_object, gof_result = run_single_configuration(*task)

          """ write config to file"""
          success_config = io.append_obj_to_pickle(obj=gof_object, file_handle=file_handle_configs)
          print("appending to file was not successful for task: ", task) if not success_config else None

          """ write result to file"""
          gof_result_df = get_results_dataframe(results=gof_result, index=i)
          success_result = io.append_result_to_csv(file_handle_results, gof_result_df, index=i)
          print("appending to file was not successful for task: ", task) if not success_result else None

          if i % 50 == 0:
            """ write to file batch-wise to prevent memory overflow """
            file_handle_results.close()
            file_handle_results = open(file_results, "a")
            file_handle_configs.close()
            file_handle_configs = open(file_configurations, "a+b")
            gc.collect()

        except Exception as e:
          print("error in task: ", i+1, " configuration: ", task)
          print(str(e))




def run_single_configuration(estimator, simulator, n_observations):
  gof = GoodnessOfFit(estimator=estimator, probabilistic_model=simulator, n_observations=n_observations, n_x_cond=1)
  return gof, gof.compute_results()


def get_results_dataframe(results, index):
  """
  retrieves the dataframe for one or more GoodnessOfFitResults result objects.
    Args:
      results: a list or single object of type GoodnessOfFitResults
    Returns:
       a pandas dataframe
  """
  n_results = len(results)
  assert n_results > 0, "no results given"
  columns = ['estimator', 'simulator', 'n_observations', 'ndim_x', 'ndim_y', 'n_centers', 'kl_divergence', 'hellinger_distance',
             'js_divergence']


  result_dicts = results.report_dict()

  return pd.DataFrame(result_dicts, columns=columns, index=[index])

def export_results(results, output_dir=None, file_name=None, export_pickle=False, export_csv=False):
  assert len(results) > 0, "no results given"

  columns = ['estimator', 'simulator', 'n_observations', 'ndim_x', 'ndim_y', 'n_centers', 'kl_divergence', 'hellinger_distance',
             'js_divergence']

  result_dicts = [result.report_dict() for result in results]
  df = pd.DataFrame(result_dicts).reindex(columns, axis=1)


  if export_pickle:
    io.store_dataframe(df, output_dir, file_name)
  if export_csv:
    io.store_csv(df, output_dir, file_name)


def merge_names(a, b):
    return '{} & {}'.format(a, b)


def merge_names_unpack(args):
    return merge_names(*args)


@contextmanager
def poolcontext(*args, **kwargs):
    pool = multiprocessing.Pool(*args, **kwargs)
    yield pool
    pool.terminate()


def main():
  conf_est, conf_sim = prepare_configurations()
  tasks = create_configurations(conf_est, conf_sim, 100) # np.arange(100, 10000, 100)
  run_configurations(tasks, output_dir="./", prefix_filename="all_configs", parallelized=False)



if __name__ == "__main__": main()