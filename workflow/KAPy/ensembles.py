"""
#Setup for debugging with VS code 
import os
os.chdir("..")
import KAPy
os.chdir("..")
config=KAPy.getConfig("./config/config.yaml")  
wf=KAPy.getWorkflow(config)
outFile=[next(iter(wf['ensstats'].keys()))]
inFiles=wf['ensstats'][outFile[0]]
%matplotlib inline
"""

import xarray as xr
from xclim import ensembles
import numpy as np

def generateEnsstats(config, inFiles, outFile):
    # Setup the ensemble
    # Given that all input files have been regridded onto a common grid,
    # they can then be concatenated into a single object. There are
    # two approachs. Previously we have used the create_ensemble from xclim.ensembles
    # However, this is quite fancy, and does a lot of logic about calendars that
    # create further problems. It also doesn't seem to handle cftime calendars at all well
    # Instead, we do it by directly opening the files with open_mfdataset, and then
    # loading it into ram
    thisEns = xr.open_mfdataset(inFiles, 
                                concat_dim="realization", 
                                combine="nested",
                                coords="all",
                                use_cftime=True)
    thisEns=thisEns.compute()

    #Calculate number of ensemble members at each point
    ensN=(~np.isnan(thisEns)).sum(dim="realization")
    ensN=ensN.rename({"indicator": "indicator_n","delta":"delta_n"})
    
    # Calculate the statistics
    ensStats = ensembles.ensemble_mean_std_max_min(thisEns)

    #Calculate the percentiles and transpose to a more friendly order
    ptileList=sorted([x for x in config["ensembles"].values()])
    ensPercs = ensembles.ensemble_percentiles(thisEns, split=False, values=ptileList)
    if "periodID" in ensPercs.indicator.dims:
        ensPercs=ensPercs.transpose("periodID","seasonID","percentiles",...)
    else:
        ensPercs=ensPercs.transpose("time","seasonID","percentiles",...)
    ensPercs=ensPercs.rename({"indicator": "indicator_percentiles","delta":"delta_percentiles"})

    # Combine results, sort and write
    ensOut = xr.merge([ensStats, ensPercs,ensN])
    sorted_vars = sorted(ensOut.data_vars)  # Get sorted variable names
    ensOut = ensOut[sorted_vars]  # Reorder dataset
    ensOut.to_netcdf(outFile[0])
