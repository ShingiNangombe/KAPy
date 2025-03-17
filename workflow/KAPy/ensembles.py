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
"""

import xarray as xr
import xclim.ensembles as xcEns


def generateEnsstats(config, inFiles, outFile):
    # Setup the ensemble
    # Given that all input files have been regridded onto a common grid,
    # they can then be concatenated into a single object. There are
    # two approachs. Previously we have used the create_ensemble from xclim.ensembles
    # However, this is quite fancy, and does a lot of logic about calendars that
    # create further problems. It also doesn't seem to handle cftime calendars at all well
    # Instead, we do it by directly opening the files with open_mfdataset. 
    thisEns = xr.open_mfdataset(inFiles, 
                                concat_dim="realization", 
                                combine="nested",
                                coords="all",
                                use_cftime=True)
    # Calculate the statistics
    ensStats = xcEns.ensemble_mean_std_max_min(thisEns)

    #Calculate the percentiles and transpose to a more friendly order
    ensPercs = xcEns.ensemble_percentiles(
        thisEns, split=False, values=[x for x in config["ensembles"].values()]
    )
    if "periodID" in ensPercs.indicator.dims:
        ensPercs=ensPercs.transpose("periodID","seasonID","percentiles",...)
    else:
        ensPercs=ensPercs.transpose("time","seasonID","percentiles",...)

    # Write results
    ensOut = xr.merge([ensStats, ensPercs])
    ensOut.to_netcdf(outFile[0])
