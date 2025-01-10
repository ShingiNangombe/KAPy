"""
import os
os.chdir("..")
os.chdir("..")
thisPath='outputs/1.primVars/pr_KA-ba_rcp26_EUR-11_CCCma-CanESM2r1i1p1_CLMcom-CCLM4-8-17_v1_day_19510101-20051231_DENMARK.pkl'
"""

import pickle
import xarray as xr
import os
import importlib


def readFile(thisPath,format=None):
    # Reads a dataset from disk, determining dynmaically whether it is
    # pickled or NetCDF based on the file extension
    if format==None:
        format = os.path.splitext(os.path.basename(thisPath))[1]
    if format == ".nc":
        thisDat = xr.open_dataarray(thisPath,
                                    use_cftime=True)
    elif format == ".pkl":  # Read pickle
        with open(thisPath, "rb") as f:
            thisDat = pickle.load(f)
    else:
        raise IOError(f"Unknown file format, '{format}' inferred from: '{thisPath}'.")
    return thisDat


def timeslice(this,startYr,endYr):
    # Slice dataset
    timemin = this.time.dt.year >= int(startYr)
    timemax = this.time.dt.year <= int(endYr)
    sliced = this.sel(time=timemin & timemax)
    return sliced

def getExternalFunction(scriptPath,functionName):
    """
    Retrieves a function from an external file 

    Args:
        scriptPath (_type_): Path to the script file containing the function
        functionName (_type_): Name of the function to retrieve
    """
    thisSpec = importlib.util.spec_from_file_location("customScript", scriptPath)
    thisModule = importlib.util.module_from_spec(thisSpec)
    thisSpec.loader.exec_module(thisModule)
    thisFn = getattr(thisModule, functionName)
    return(thisFn)
