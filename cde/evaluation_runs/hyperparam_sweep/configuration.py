import matplotlib as mpl
mpl.use("PS") #handles X11 server detection (required to run on console)
import numpy as np
import argparse
import os

from cde.evaluation.GoodnessOfFitResults import GoodnessOfFitResults

from cde.evaluation.ConfigRunner import ConfigRunner
from ml_logger import logger

EXP_PREFIX = 'hyperparam_sweep'
RESULTS_FILE = 'results.pkl'

def question1():
  estimator_params = {
  'KernelMixtureNetwork':

    {'center_sampling_method': ["k_means", "all"],
     'n_centers': [20, 50],
     'keep_edges': [True],
     'init_scales': [[0.1, 0.5, 1.]],
     'train_scales': [True, False],
     'hidden_sizes': [(16, 16)],
     'n_training_epochs': [1000],
     'x_noise_std': [None],
     'y_noise_std': [None],
     'random_seed': [22],
     'weight_normalization': [True],
     'data_normalization': [True, False]
     },
  'MixtureDensityNetwork':
    {
      'n_centers': [10, 20],
      'n_training_epochs': [1000],
      'hidden_sizes': [(16, 16)],
      'x_noise_std': [None],
      'y_noise_std': [None],
      'random_seed': [22],
      'weight_normalization': [True],
      'data_normalization': [True, False]

    }
  }

  simulators_params = {
  'EconDensity': {'std': [1],
                  'heteroscedastic': [True],
                  },

  'GaussianMixture': {'n_kernels' : [10],
                      'ndim_x': [2],
                      'ndim_y': [2],
                      'means_std': [1.5]
                      },
  'ArmaJump': {'c': [0.1],
               'arma_a1': [0.9],
               'std': [0.05],
               'jump_prob': [0.05],
              },
  'SkewNormal': {}
  }


  return estimator_params, simulators_params


if __name__ == '__main__':

  parser = argparse.ArgumentParser(description='Run configuration script')
  parser.add_argument('--parallel', type=bool, default=True,
                      help='an integer for the accumulator')
  parser.add_argument('--n_workers', type=int, default=1,
                      help='sum the integers (default: find the max)')
  parser.add_argument('--use_gpu', type=bool, default=False)
  args = parser.parse_args()

  if not args.use_gpu:
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

  run = True
  load = not run

  keys_of_interest = ['task_name', 'estimator', 'simulator', 'n_observations', 'center_sampling_method', 'x_noise_std',
                      'y_noise_std', 'ndim_x', 'ndim_y', 'n_centers', "n_mc_samples", "n_x_cond", 'mean_est',
                      'cov_est', 'mean_sim', 'cov_sim', 'kl_divergence', 'hellinger_distance', 'js_divergence',
                      'x_cond', 'random_seed', "mean_sim", "cov_sim", "mean_abs_diff", "cov_abs_diff",
                      "VaR_sim", "VaR_est", "VaR_abs_diff", "CVaR_sim", "CVaR_est", "CVaR_abs_diff",
                      "time_to_fit"
                      ]


  if run:
      observations = 100 * np.logspace(0, 5, num=6, base=2.0,
                                       dtype=np.int32)  # creates a list with log scale: 100, 200, 400, 800, 1600

      conf_est, conf_sim = question1()
      conf_runner = ConfigRunner(EXP_PREFIX, conf_est, conf_sim, observations=observations, keys_of_interest=keys_of_interest,
                                 n_mc_samples=2e6, n_x_cond=10, n_seeds=5)

      conf_runner.run_configurations(dump_models=True, multiprocessing=args.parallel, n_workers=args.n_workers)





  if load:
    results_from_pkl_file = dict(logger.load_pkl(RESULTS_FILE))
    gof_result = GoodnessOfFitResults(single_results_dict=results_from_pkl_file)
    results_df = gof_result.generate_results_dataframe(keys_of_interest)


    graph_dicts = [
      {"estimator": "KernelMixtureNetwork", "x_noise_std": 0.1, "y_noise_std": None, "n_centers": 20},
      {"estimator": "KernelMixtureNetwork", "x_noise_std": 0.01, "y_noise_std": None, "n_centers": 20},
      {"estimator": "KernelMixtureNetwork", "x_noise_std": None, "y_noise_std": None, "n_centers": 20},
      {"estimator": "MixtureDensityNetwork", "x_noise_std": 0.1, "y_noise_std": None, "n_centers": 10},
      { "estimator": "MixtureDensityNetwork", "x_noise_std": 0.01, "y_noise_std": None, "n_centers": 10},
      {"estimator": "MixtureDensityNetwork", "x_noise_std": None, "y_noise_std": None, "n_centers": 10}
    ]

    gof_result.plot_metric(graph_dicts, metric="kl_divergence", simulator="EconDensity")
    print(gof_result)

