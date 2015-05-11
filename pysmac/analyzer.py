from __future__ import print_function

import os
import glob
import six
import re
#import operator


import numpy as np
import matplotlib.pyplot as plt
#import matplotlib.cm as pltcm
#from matplotlib.widgets import CheckButtons

import sys
sys.path.append('/home/sfalkner/repositories/github/pysmac/')


import pysmac.remote_smac
import pysmac.utils.smac_output_readers as smac_readers


class SMAC_analyzer(object):
   
    # collects smac specific data that goes into the scenario file
    def __init__(self, obj):
        
        if isinstance(obj,pysmac.remote_smac.remote_smac):
            self.scenario_fn = os.path.join(obj.working_directory, 'scenario.dat')
        self.scenario_fn = str(obj)
        
        # if it is a string, it can be a directory or a file
        if isinstance(obj, six.string_types):
            if os.path.isfile(obj):
                self.scenario_fn=obj
            else:
                self.scenario_fn=os.path.join(obj, 'scenario.dat')
        
        self.validation = True
        self.overall_objective = "MEAN10"
        
        # parse scenario file for important information
        with open(self.scenario_fn,'r') as fh:
            for line in fh.readlines():
                strlist = line.split()
                
                if strlist[0] in {'output-dir', 'outputDirectory', 'outdir'}:
                    self.output_dir = strlist[1]
                
                if strlist[0] in {'pcs-file'}:
                    self.pcs_fn = strlist[1]
                
                if strlist[0] == 'validation':
                    self.validation = bool(strlist[1])
                    
                if strlist[0] in {'intra-obj', 'intra-instance-obj', 'overall-obj', 'intraInstanceObj', 'overallObj', 'overall_obj','intra_instance_obj'}:
                    self.overall_objective = strlist[1]
                
                if strlist[0] in {'algo-cutoff-time','target-run-cputime-limit', 'target_run_cputime_limit', 'cutoff-time', 'cutoffTime', 'cutoff_time'}:
                    self.cutoff_time = float(strlist[1])
                            
        # find the number of runs
        self.scenario_output_dir = (os.path.join(self.output_dir,
            os.path.basename(''.join(self.scenario_fn.split('.')[:-1]))))
        
        tmp = glob.glob( os.path.join(self.scenario_output_dir, "traj-run-*.txt"))
        
        # create the data dict for every run index
        self.data = {}
        for fullname in tmp:
            filename = (os.path.basename(fullname))
            run_id = re.match("traj-run-(\d*).txt",filename).group(1)
            self.data[int(run_id)]={}
        
        # for now, we only load the incumbents for each run
        
        for i in self.data.keys():
            try:
                # with test instances, the validation runs are loaded
                if self.validation:
                    configs = smac_readers.read_validationCallStrings_file(
                        os.path.join(self.scenario_output_dir,
                            "validationCallStrings-traj-run-{}-walltime.csv".format(i)))
                    test_performances = smac_readers.read_validationObjectiveMatrix_file(
                        os.path.join(self.scenario_output_dir,
                            "validationObjectiveMatrix-traj-run-{}-walltime.csv".format(i)))
            
                # without validation, there are only trajectory files to pase
                else:
                    raise NotImplemented("The handling of cases without validation runs is not yet implemented")
                self.data[i]['parameters'] = configs
                self.data[i]['test_performances'] = test_performances
            except:
                print("Failed to load data for run {}. Please make sure it has finished properly.\nDropping it for now.".format(i))
                self.data.pop(i)

    def get_pyfanova_obj(self, improvement_over='DEFAULT', check_scenario_files = True):
        try:
            import pyfanova.fanova
            
            self.merged_dir = os.path.join(self.output_dir,"merged_run")
            
            # delete existing merged run folder
            if os.path.exists(self.merged_dir):
                import shutil
                shutil.rmtree(self.merged_dir)

            from pysmac.utils.state_merge import state_merge
            
            print(os.path.join(self.scenario_output_dir, 'state-run*'))
            print(glob.glob(os.path.join(self.scenario_output_dir, 'state-run*')))
            
            state_merge(glob.glob(os.path.join(self.scenario_output_dir, 'state-run*')),
                            self.merged_dir, check_scenario_files = check_scenario_files)
            

            return(pyfanova.fanova.Fanova(self.merged_dir, improvement_over=improvement_over))
                
        except ImportError:
            raise
            raise NotImplementedError('To use this feature, please install the pyfanova package.')
        except:
            print('Something went during the initialization of the FANOVA.')
            raise

    def get_item_all_runs(self, func = lambda d: d['function value']):
        return (map(lambda run: map(func, run[1:]), self.data_all_runs))
    
    def get_item_single_run(self, run_id, func = lambda d: d['function value']):
        return map(func,self.data_all_runs[run_id][1:])
    
    def plot_run_performance(self, runs = None):    

        plot = interactive_plot()
        
        for i in range(len(self.data_all_runs)):
            y = self.get_item_single_run(i)
            x = range(len(y))
            plot.scatter(self.data_all_runs[i][0], x,y, self.get_item_single_run(i, func = lambda d: '\n'.join(['%s=%s'%(k,v) for (k,v) in d['parameter settings'].items() ]) ), color = self.cm[i])
        
        plot.add_datacursor()
        plot.show()

            
    def plot_run_incumbent(self, runs = None):    
        plot = interactive_plot()
        
        for i in range(len(self.data_all_runs)):
            y = np.minimum.accumulate(self.get_item_single_run(i))
            #x = 
            _ , indices = np.unique(y, return_index = True)
            print(indices)
            
            indices = np.append(indices[::-1], len(y)-1)
            print(indices)
            x = np.arange(len(y))[indices]
            y = y[indices]
            
            print(x,y)
            print('='*40)
            plot.step(self.data_all_runs[i][0], x, y, color = self.cm[i])
        
        plot.add_datacursor(formatter = 'iteration {x:.0f}: {y}'.format)
        plot.show()
        
        
    def basic_analysis (self):
        
        fig, ax = plt.subplots()
        
        ax.set_title('function value vs. number of iterations')
        ax.set_xlabel('iteration')
        ax.set_ylabel('function value')
        
        for i in range(len(self.trajectory)):
            color='red' if i == self.incumbent_index else 'blue'
            ax.scatter( i, self.trajectory[i][0], color=color, label = '\n'.join(['%s = %s' % (k,v) for (k, v) in self.trajectory[i][2].items()]))

        datacursor(
            bbox=dict(alpha=1),
            formatter = 'iteration {x:.0f}: {y}\n{label}'.format,
            hover=False,
            display='multiple',
            draggable=True,
            horizontalalignment='center',
            hide_button = 3)
        
        fig, ax = plt.subplots()
        incumbents = np.minimum.accumulate(map(itemgetter(0), self.trajectory))
        ax.step(range(len(incumbents)), incumbents)
        
        plt.show()